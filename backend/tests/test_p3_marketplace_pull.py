"""P3 contract (revision 4), Section 3 -- the Pull adapter: checkpoint ordering, the shared rate
gate across all three callers, and chunked backfill. Fixture-based throughout via an injected
`fetch` callable; no live IndiaMART call anywhere in this file."""

from datetime import UTC, datetime, timedelta

from app.core import marketplace_imports as mi
from app.core import marketplace_pull as pull

ACCOUNT_ID = "default"


def _item(unique_id, minute=0):
    return {
        "UNIQUE_QUERY_ID": unique_id,
        "QUERY_TIME": f"01-OCT-2026 10:{minute:02d}:00",
        "QUERY_TYPE": "W",
        "SENDER_NAME": "Fixture Buyer",
        "SENDER_MOBILE": "9000000001",
    }


def test_pull_captures_and_advances_checkpoint_only_after_capture_commits(db_session):
    calls = []

    def fetch(api_key, start, end):
        calls.append((start, end))
        return [_item("Q-P1"), _item("Q-P2", minute=1)]

    now = datetime.now(UTC).replace(tzinfo=None)
    result = pull.run_pull_once(db_session, account_id=ACCOUNT_ID, fetch=fetch, api_key="fixture-key", now=now)

    assert result.ran is True
    assert len(result.capture.captured_ids) == 2
    assert mi.get_checkpoint(db_session) == now  # advanced only after capture_batch's own commit


def test_checkpoint_case_3a_not_advanced_when_capture_itself_fails(db_session, monkeypatch):
    """Case 3a: simulate a crash DURING Capture -- checkpoint must not move past that window."""
    now = datetime.now(UTC).replace(tzinfo=None)

    def failing_capture(db, *, items, account_id, platform="indiamart", received_via="pull"):
        raise RuntimeError("simulated crash mid-capture")

    monkeypatch.setattr(mi, "capture_batch", failing_capture)

    try:
        pull.run_pull_once(db_session, account_id=ACCOUNT_ID, fetch=lambda *a: [_item("Q-P3")], api_key="fixture-key", now=now)
        assert False, "expected the simulated crash to propagate"
    except RuntimeError:
        pass

    assert mi.get_checkpoint(db_session) is None  # never advanced -- next run re-fetches the same window


def test_shared_rate_gate_blocks_a_second_caller_within_the_window(db_session):
    """A scheduled Pull run and a Verify-key-now call within 5 minutes -- only one actually calls
    IndiaMART; the other is held by the shared gate, not executed as an independent call."""
    now = datetime.now(UTC).replace(tzinfo=None)
    first = pull.run_pull_once(db_session, account_id=ACCOUNT_ID, fetch=lambda *a: [], api_key="fixture-key", now=now)
    assert first.ran is True

    verify_calls = []
    second = pull.verify_key_now(
        db_session, account_id=ACCOUNT_ID, fetch=lambda *a: verify_calls.append(a) or [], api_key="fixture-key",
    )
    assert second.ok is False
    assert second.reason == "rate_gate_held"
    assert not verify_calls  # the fetch function itself was never invoked


def test_backfill_chunks_respect_the_seven_day_limit(db_session):
    chunk_windows = []

    def fetch(api_key, start, end):
        chunk_windows.append((start, end))
        return []

    range_start = datetime(2026, 1, 1)
    range_end = datetime(2026, 1, 20)  # 19 days -> 3 chunks of <=7 days
    results = pull.run_backfill(
        db_session, account_id=ACCOUNT_ID, range_start=range_start, range_end=range_end, fetch=fetch, api_key="fixture-key",
        now=datetime.now(UTC).replace(tzinfo=None),  # simulates the real 5-minute gaps between chunks, without sleeping
    )
    assert all(r.ran for r in results)
    assert len(results) == 3
    for r in results:
        assert (r.window_end - r.window_start) <= timedelta(days=7)
    assert results[0].window_start == range_start
    assert results[-1].window_end == range_end


def test_backfill_never_races_a_concurrent_caller_for_the_gate(db_session):
    """A backfill chunk and the regular scheduled job never race each other for the key -- if the
    gate is already held, the backfill stops rather than skipping ahead out of order."""
    now = datetime.now(UTC).replace(tzinfo=None)
    mi.try_acquire_rate_gate(db_session, now=now)  # simulates a concurrent scheduled Pull run holding the gate

    results = pull.run_backfill(
        db_session,
        account_id=ACCOUNT_ID,
        range_start=datetime(2026, 1, 1),
        range_end=datetime(2026, 1, 10),
        fetch=lambda *a: [],
        api_key="fixture-key",
    )
    assert len(results) == 1
    assert results[0].ran is False
    assert results[0].reason == "rate_gate_held"
