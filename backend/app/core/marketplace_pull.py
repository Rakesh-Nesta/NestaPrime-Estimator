"""P3 contract (revision 4), Section 3: the Pull adapter. `fetch_window` is the one place that
would ever make a real outbound HTTP call to IndiaMART -- everywhere else in this module (and
every test) works against an injected callable, so fixture-based development and testing never
needs a live key. The default `fetch_window` implementation is here for completeness and is never
exercised by this session's own tests; nothing schedules it yet (no cron/scheduler activation is
part of this contract's authorised scope, Section 0)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

import httpx

from app.config import settings
from app.core import marketplace_imports as mi
from sqlalchemy.orm import Session

INDIAMART_PULL_URL = "https://mapi.indiamart.com/wservce/crm/crmListing/v2/"
MAX_WINDOW = timedelta(days=7)  # IndiaMART's own per-call limit (Section 3)

FetchFn = Callable[[str, datetime | None, datetime | None], list[dict]]
"""(api_key, start_time, end_time) -> list of raw lead dicts. Both times None means "since last
hit, within 24h" (IndiaMART's own documented default when both are omitted)."""


class KeyNotConfigured(Exception):
    pass


def default_fetch_window(api_key: str, start_time: datetime | None, end_time: datetime | None) -> list[dict]:
    """The real IndiaMART Pull call -- never used by this session's tests (no live key
    verification is part of this contract's authorised scope). glusr_crm_key is a query
    parameter, never a header (Section 3); never logged here or anywhere else."""
    if not api_key:
        raise KeyNotConfigured("INDIAMART_PULL_API_KEY is not configured")
    params = {"glusr_crm_key": api_key}
    if start_time is not None:
        params["start_time"] = start_time.strftime("%d-%m-%Y%H:%M:%S")
    if end_time is not None:
        params["end_time"] = end_time.strftime("%d-%m-%Y%H:%M:%S")
    response = httpx.get(INDIAMART_PULL_URL, params=params, timeout=30)
    response.raise_for_status()
    body = response.json()
    return body.get("RESPONSE", []) if isinstance(body, dict) else []


@dataclass
class PullRunResult:
    ran: bool
    reason: str | None = None
    capture: mi.CaptureResult | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


def run_pull_once(
    db: Session,
    *,
    account_id: str,
    fetch: FetchFn | None = None,
    api_key: str | None = None,
    now: datetime | None = None,
) -> PullRunResult:
    """One scheduled-job tick. Acquires the shared rate gate first (Section 3) -- if another
    caller (backfill, verify-key) already holds it, this run does nothing and reports why, rather
    than racing it. Fetches the window since the last checkpoint (or "last 24h" if there is none
    yet), captures every item as one durable batch, and advances the checkpoint only after that
    batch has actually committed -- never before, and never partially."""
    # `fetch` resolves to the CURRENT default_fetch_window at call time, not at import time --
    # a default *parameter value* is bound once, at function-definition time, which would make it
    # immune to a test's own monkeypatch of the module-level name (a real bug found via testing).
    fetch = fetch if fetch is not None else default_fetch_window
    api_key = api_key if api_key is not None else settings.indiamart_pull_api_key
    now = now or datetime.now(UTC).replace(tzinfo=None)

    if not mi.try_acquire_rate_gate(db, now=now):
        return PullRunResult(ran=False, reason="rate_gate_held")

    checkpoint = mi.get_checkpoint(db)
    window_start = checkpoint  # None means "since last hit, within 24h" per IndiaMART's own default
    window_end = now

    items = fetch(api_key, window_start, window_end)
    capture = mi.capture_batch(db, items=items, account_id=account_id)
    mi.advance_checkpoint(db, end_time=window_end)  # only after capture_batch's own commit succeeded
    return PullRunResult(ran=True, capture=capture, window_start=window_start, window_end=window_end)


@dataclass
class BackfillChunkResult:
    window_start: datetime
    window_end: datetime
    ran: bool
    reason: str | None = None
    capture: mi.CaptureResult | None = None


def run_backfill(
    db: Session,
    *,
    account_id: str,
    range_start: datetime,
    range_end: datetime,
    fetch: FetchFn | None = None,
    api_key: str | None = None,
    now: datetime | None = None,
) -> list[BackfillChunkResult]:
    """Section 3: chunks into <=7-day windows, acquiring the same shared rate gate before each
    chunk -- a backfill in progress and the regular scheduled job never race each other for the
    key. Progress is returned per-chunk, not as one opaque long-running call.

    Real-world consequence, worth stating plainly: the shared gate's own 5-minute-between-calls
    rule (Section 3) means a multi-chunk backfill can genuinely process only ONE chunk per
    real-world 5-minute window -- this function does not block/sleep to wait out that interval
    (an HTTP request handler must not), so a chunk that finds the gate already held stops the
    whole call there, reporting exactly how far it got; the caller re-invokes this same function
    (e.g. the operational screen's own "Run backfill" action, called again) to continue from
    where a resumed range_start would pick back up. `now` exists only so tests can simulate real
    time genuinely elapsing between chunks without an actual multi-minute sleep; production calls
    never pass it, so production always uses the real wall clock and the real constraint."""
    fetch = fetch if fetch is not None else default_fetch_window
    api_key = api_key if api_key is not None else settings.indiamart_pull_api_key
    results: list[BackfillChunkResult] = []
    cursor = range_start
    clock = now
    while cursor < range_end:
        chunk_end = min(cursor + MAX_WINDOW, range_end)
        if not mi.try_acquire_rate_gate(db, now=clock):
            results.append(BackfillChunkResult(window_start=cursor, window_end=chunk_end, ran=False, reason="rate_gate_held"))
            break
        items = fetch(api_key, cursor, chunk_end)
        capture = mi.capture_batch(db, items=items, account_id=account_id)
        results.append(BackfillChunkResult(window_start=cursor, window_end=chunk_end, ran=True, capture=capture))
        cursor = chunk_end
        if clock is not None:
            clock = clock + mi.RATE_GATE_MIN_INTERVAL
    return results


@dataclass
class VerifyKeyResult:
    ok: bool
    reason: str | None = None


def verify_key_now(db: Session, *, account_id: str, fetch: FetchFn | None = None, api_key: str | None = None) -> VerifyKeyResult:
    """Section 8's "Verify key now" -- a single on-demand read-only call, through the same shared
    rate gate as every other IndiaMART call, so it can never collide with a scheduled Pull or a
    backfill chunk in progress. A narrow, recent window only -- never a real Capture."""
    fetch = fetch if fetch is not None else default_fetch_window
    api_key = api_key if api_key is not None else settings.indiamart_pull_api_key
    if not api_key:
        return VerifyKeyResult(ok=False, reason="not_configured")
    if not mi.try_acquire_rate_gate(db):
        return VerifyKeyResult(ok=False, reason="rate_gate_held")
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        fetch(api_key, now - timedelta(hours=1), now)
        return VerifyKeyResult(ok=True)
    except Exception as exc:  # noqa: BLE001 -- any failure means "not currently verified," not a 500
        return VerifyKeyResult(ok=False, reason=str(exc)[:200])
