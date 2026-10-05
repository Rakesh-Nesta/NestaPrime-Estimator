"""P3 contract (revision 4), Section 8/9: the operational screen (PM/Director only) and the
Marketing Phase A aggregate dashboard (a new, narrow, aggregates-only endpoint -- Marketing is
added to this one role gate and nowhere else)."""

import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import marketplace_imports as mi
from app.core import marketplace_pull as pull
from app.core.auth import require_roles
from app.config import settings
from app.db.session import get_db
from app.models.marketplace_lead_import import (
    MarketplaceApiRateGate,
    MarketplaceLeadImport,
    MarketplaceLeadImportStatus,
    MarketplacePullCheckpoint,
)
from app.models.notification import Notification, NotificationKind
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.user import User, UserRole

router = APIRouter(prefix="/marketplace-imports", tags=["marketplace-imports"])

# Section 2/8: matches the ledger's own read-access gate -- PM/Director only.
OPS_ROLES = ("pm", "director")
MARKETING_ROLES = ("marketing", "pm", "director")

ACCOUNT_ID = "default"  # single-account NestaPrime setup, per the contract's own Section 2 note


def _mask_key(key: str) -> str | None:
    if not key:
        return None
    return f"...{key[-6:]}" if len(key) > 6 else "...(short)"


class ConnectionHealthOut(BaseModel):
    configured: bool
    masked_key: str | None
    last_call_at: datetime | None
    checkpoint: datetime | None


@router.get("/connection-health", response_model=ConnectionHealthOut)
def get_connection_health(db: Session = Depends(get_db), current_user=Depends(require_roles(*OPS_ROLES))):
    """Section 6/8: connection status and a masked key fragment only -- the real key is never
    returned by any endpoint, ever, not even to Director."""
    gate = db.get(MarketplaceApiRateGate, "indiamart")
    checkpoint = db.get(MarketplacePullCheckpoint, "indiamart")
    return ConnectionHealthOut(
        configured=bool(settings.indiamart_pull_api_key),
        masked_key=_mask_key(settings.indiamart_pull_api_key),
        last_call_at=gate.last_call_at if gate else None,
        checkpoint=checkpoint.last_captured_end_time if checkpoint else None,
    )


class SummaryOut(BaseModel):
    backlog_count: int
    oldest_pending_received_at: datetime | None
    quarantined_count: int
    failures_count: int
    expired_count: int


@router.get("/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db), current_user=Depends(require_roles(*OPS_ROLES))):
    """Section 8's Backlog/Quarantined/Failures/Expired counts -- informational only, the
    lock-and-process mechanism (Section 2) is automatic and needs no action here."""
    q = db.query(MarketplaceLeadImport)
    oldest_pending = (
        q.filter(MarketplaceLeadImport.status == MarketplaceLeadImportStatus.PENDING)
        .order_by(MarketplaceLeadImport.received_at.asc())
        .first()
    )
    return SummaryOut(
        backlog_count=q.filter(MarketplaceLeadImport.status == MarketplaceLeadImportStatus.PENDING).count(),
        oldest_pending_received_at=oldest_pending.received_at if oldest_pending else None,
        quarantined_count=q.filter(MarketplaceLeadImport.status == MarketplaceLeadImportStatus.QUARANTINED).count(),
        failures_count=q.filter(MarketplaceLeadImport.status == MarketplaceLeadImportStatus.REJECTED).count(),
        expired_count=q.filter(MarketplaceLeadImport.status == MarketplaceLeadImportStatus.EXPIRED).count(),
    )


class LedgerRowOut(BaseModel):
    id: uuid.UUID
    external_id: str | None
    enquiry_time: datetime | None
    received_at: datetime
    status: str
    rejection_reason: str | None
    retry_count: int
    manually_retried_at: datetime | None
    opportunity_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[LedgerRowOut])
def list_ledger_rows(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OPS_ROLES)),
):
    """PM/Director-only read of the ledger itself (Section 2), backing the operational screen's
    Quarantined/Failures/Expired lists. raw_payload is deliberately NOT included in this response
    shape -- the operational screen shows status/reason, not the raw buyer PII."""
    query = db.query(MarketplaceLeadImport)
    if status is not None:
        query = query.filter(MarketplaceLeadImport.status == status)
    return query.order_by(MarketplaceLeadImport.received_at.desc()).limit(200).all()


class VerifyKeyOut(BaseModel):
    ok: bool
    reason: str | None = None


def _notify_directors_key_expired(db: Session, reason: str) -> None:
    """Section 7/8/11: an expired/rejected key alerts every active Director, in-app only --
    exactly the same in-app-only-by-construction reasoning as _notify_import_lead_assigned
    (ownership.py): this never calls app/core/reminders.py's own gathering logic. Deduped by
    hand (not the DB unique index, since this kind has no follow_up_id to key on): at most one
    per Director per calendar day, checked directly rather than trusted."""
    today = date.today()
    directors = db.query(User).filter(User.role == UserRole.DIRECTOR, User.is_active.is_(True)).all()
    for director in directors:
        already_sent_today = (
            db.query(Notification)
            .filter(
                Notification.user_id == director.id,
                Notification.kind == NotificationKind.IMPORT_KEY_EXPIRED,
                Notification.notification_date == today,
            )
            .first()
        )
        if already_sent_today is not None:
            continue
        db.add(
            Notification(
                user_id=director.id,
                kind=NotificationKind.IMPORT_KEY_EXPIRED,
                notification_date=today,
                title="IndiaMART Pull key needs attention",
                body=f"The last verification failed: {reason}",
            )
        )
    db.commit()


@router.post("/verify-key", response_model=VerifyKeyOut)
def verify_key(db: Session = Depends(get_db), current_user=Depends(require_roles(*OPS_ROLES))):
    result = pull.verify_key_now(db, account_id=ACCOUNT_ID)
    if not result.ok and result.reason not in ("not_configured", "rate_gate_held"):
        _notify_directors_key_expired(db, result.reason or "unknown error")
    return VerifyKeyOut(ok=result.ok, reason=result.reason)


class RetryOut(BaseModel):
    converted: bool
    opportunity_id: uuid.UUID | None
    rejection_reason: str | None


@router.post("/{ledger_row_id}/retry", response_model=RetryOut)
def retry_ledger_row(
    ledger_row_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OPS_ROLES)),
):
    """Section 2/8 (revision 4 fix): synchronously attempts real processing and reports the real
    outcome immediately -- never just a status flip."""
    try:
        outcome = mi.manual_retry(db, ledger_row_id=ledger_row_id, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RetryOut(converted=outcome.converted, opportunity_id=outcome.opportunity_id, rejection_reason=outcome.rejection_reason)


class BackfillRequest(BaseModel):
    range_start: datetime
    range_end: datetime


class BackfillChunkOut(BaseModel):
    window_start: datetime
    window_end: datetime
    ran: bool
    reason: str | None
    captured: int
    quarantined: int
    duplicates: int


@router.post("/backfill", response_model=list[BackfillChunkOut])
def run_backfill(
    payload: BackfillRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OPS_ROLES)),
):
    if payload.range_end <= payload.range_start:
        raise HTTPException(status_code=400, detail="range_end must be after range_start")
    chunks = pull.run_backfill(db, account_id=ACCOUNT_ID, range_start=payload.range_start, range_end=payload.range_end)
    return [
        BackfillChunkOut(
            window_start=c.window_start,
            window_end=c.window_end,
            ran=c.ran,
            reason=c.reason,
            captured=len(c.capture.captured_ids) if c.capture else 0,
            quarantined=len(c.capture.quarantined_ids) if c.capture else 0,
            duplicates=len(c.capture.duplicate_of_ids) if c.capture else 0,
        )
        for c in chunks
    ]


# --- Section 9: Marketing Phase A aggregate dashboard ------------------------------------------
#
# Governing text, P3 contract (revision 4), Section 9: "Aggregate volume dashboard (counts by source,
# QUERY_TYPE, and date bucket) and a current-stage distribution by import cohort" -- a current-stage
# snapshot, "grouped by import cohort (leads whose enquiry_time or received_at -- stated explicitly, not
# left implicit -- falls in the selected period), showing the count currently sitting at each Opportunity
# stage as of now, with an explicit denominator (total Opportunities imported in that period)". Counts and
# rates only: never individual buyer fields, never raw payload, never full Opportunity rows.
#
# The contract leaves five things open; none is invented silently -- each is an explicit, echoed choice:
#   1. cohort basis ("enquiry_time or received_at"): the caller selects it (`basis`); the default stays
#      enquiry_time, the behaviour this endpoint already shipped with. The response echoes it.
#   2. date-bucket granularity: `bucket` = day | week | month (default day). Weeks start on Monday (ISO).
#   3. timezone: `received_at` is stored as naive UTC and is converted to IST (Asia/Kolkata, UTC+05:30) calendar days.
#      `enquiry_time` is the provider's own wall-clock value, parsed and never converted; the provider's timezone for it
#      is NOT verified (the contract states IST only for the Pull API's request window parameters), so enquiry_time
#      periods and buckets use the date exactly as recorded and the response says so rather than claiming IST.
#   4. period boundaries: [period_start 00:00, period_end + 1 day 00:00) in that calendar, so the end date is
#      inclusive to its last instant and the next midnight belongs to the next day.
#   5. denominator: Opportunities imported (ledger rows that produced an Opportunity), counted distinctly --
#      not every ledger row, which also includes pending, quarantined, rejected and expired leads.

# India has no daylight saving: IST is exactly UTC+05:30, so a fixed offset is exact and needs no timezone database
# (the production image is python:slim and requirements.txt does not pin tzdata).
IST = timezone(timedelta(hours=5, minutes=30), "IST")
TIMEZONE_NOTES = {
    "enquiry_time": "Provider-recorded time, timezone not verified: dates and buckets use the enquiry date exactly as the "
    "provider recorded it (no timezone conversion)",
    "received_at": "IST (UTC+05:30, Asia/Kolkata): received times are stored in UTC and converted; dates and buckets are "
    "IST calendar days",
}
MAX_BUCKETS = 2000  # a response-size safeguard, not a business rule: ask for a coarser bucket or a shorter period

CohortBasis = Literal["enquiry_time", "received_at"]
BucketSize = Literal["day", "week", "month"]


class StageCount(BaseModel):
    stage: str
    count: int
    rate: float  # count / imported_total (the explicit denominator); 0 impossible here, only stages with leads are listed


class DateBucketCount(BaseModel):
    bucket_start: date
    label: str
    count: int


class MarketingDashboardOut(BaseModel):
    period_start: date
    period_end: date
    cohort_basis: str
    bucket: str
    timezone: str
    received_total: int  # every ledger row (lead) in the cohort, whatever its status
    imported_total: int  # the DENOMINATOR: Opportunities imported from those leads
    excluded_missing_enquiry_time: int  # enquiry_time basis only: leads received in the period that have no enquiry_time
    by_source: dict[str, int]
    by_query_type: dict[str, int]
    by_date_bucket: list[DateBucketCount]
    current_stage_distribution: list[StageCount]


def _bucket_start(day: date, bucket: str) -> date:
    if bucket == "week":
        return day - timedelta(days=day.weekday())  # Monday
    if bucket == "month":
        return day.replace(day=1)
    return day


def _next_bucket(start: date, bucket: str) -> date:
    if bucket == "week":
        return start + timedelta(days=7)
    if bucket == "month":
        return date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start + timedelta(days=1)


def _bucket_label(start: date, bucket: str) -> str:
    if bucket == "week":
        return f"Week of {start.isoformat()}"
    if bucket == "month":
        return start.strftime("%Y-%m")
    return start.isoformat()


def _bucket_starts(period_start: date, period_end: date, bucket: str) -> list[date]:
    starts: list[date] = []
    current = _bucket_start(period_start, bucket)
    last = _bucket_start(period_end, bucket)
    while current <= last:
        starts.append(current)
        if len(starts) > MAX_BUCKETS:
            raise HTTPException(
                status_code=400,
                detail=f"This period needs more than {MAX_BUCKETS} {bucket} buckets; choose a coarser bucket (week or month) "
                "or a shorter period",
            )
        current = _next_bucket(current, bucket)
    return starts


def _ist_midnight_as_naive_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST).astimezone(UTC).replace(tzinfo=None)


def _cohort_window(basis: str, period_start: date, period_end: date) -> tuple[datetime, datetime]:
    """Half-open [start, end) in the basis column's own stored clock (see the notes above)."""
    first, after = period_start, period_end + timedelta(days=1)
    if basis == "received_at":
        return _ist_midnight_as_naive_utc(first), _ist_midnight_as_naive_utc(after)
    return datetime.combine(first, time.min), datetime.combine(after, time.min)


def _local_date(basis: str, value: datetime) -> date:
    if basis == "received_at":
        return value.replace(tzinfo=UTC).astimezone(IST).date()
    return value.date()


@router.get("/marketing/dashboard", response_model=MarketingDashboardOut)
def get_marketing_dashboard(
    period_start: date,
    period_end: date,
    basis: CohortBasis = "enquiry_time",
    bucket: BucketSize = "day",
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MARKETING_ROLES)),
):
    """Section 9 (revision 4): see the notes above. A CURRENT-STAGE SNAPSHOT grouped by import cohort,
    not a historical conversion funnel (that would need Opportunity stage-change history from audit_log,
    not built). Counts and rates only. query_type comes from the ledger's own durable column, so the
    grouping keeps working after the 90-day retention purge removes raw_payload."""
    if period_end < period_start:
        raise HTTPException(status_code=400, detail="period_end must not be before period_start")
    bucket_starts = _bucket_starts(period_start, period_end, bucket)  # also bounds the response size, before any query
    window_start, window_end = _cohort_window(basis, period_start, period_end)
    cohort_column = MarketplaceLeadImport.enquiry_time if basis == "enquiry_time" else MarketplaceLeadImport.received_at
    in_window = (cohort_column >= window_start, cohort_column < window_end)

    rows = (
        db.query(MarketplaceLeadImport.platform, MarketplaceLeadImport.query_type, cohort_column)
        .filter(cohort_column.isnot(None))
        .filter(*in_window)
        .all()
    )
    by_source: dict[str, int] = {}
    by_query_type: dict[str, int] = {}
    per_bucket = {start: 0 for start in bucket_starts}
    for platform, query_type, value in rows:
        by_source[platform] = by_source.get(platform, 0) + 1
        key = query_type or "unknown"
        by_query_type[key] = by_query_type.get(key, 0) + 1
        per_bucket[_bucket_start(_local_date(basis, value), bucket)] += 1

    # The denominator and the stage distribution come from the same set: distinct Opportunities that the cohort's
    # leads produced. Ledger rows without an Opportunity (pending, quarantined, rejected, expired) are volume, not imports.
    imported_ids = (
        select(MarketplaceLeadImport.opportunity_id)
        .where(MarketplaceLeadImport.opportunity_id.isnot(None))
        .where(cohort_column.isnot(None), *in_window)
    )
    stage_rows = (
        db.query(Opportunity.stage, func.count(Opportunity.id))
        .filter(Opportunity.id.in_(imported_ids))
        .group_by(Opportunity.stage)
        .all()
    )
    stage_counts = {(s.value if isinstance(s, OpportunityStage) else s): n for s, n in stage_rows}
    imported_total = sum(stage_counts.values())
    ordered_stages = [s.value for s in OpportunityStage if stage_counts.get(s.value)]

    excluded = 0
    if basis == "enquiry_time":
        received_start, received_end = _cohort_window("received_at", period_start, period_end)
        excluded = (
            db.query(func.count(MarketplaceLeadImport.id))
            .filter(MarketplaceLeadImport.enquiry_time.is_(None))
            .filter(MarketplaceLeadImport.received_at >= received_start, MarketplaceLeadImport.received_at < received_end)
            .scalar()
        ) or 0

    return MarketingDashboardOut(
        period_start=period_start,
        period_end=period_end,
        cohort_basis=basis,
        bucket=bucket,
        timezone=TIMEZONE_NOTES[basis],
        received_total=len(rows),
        imported_total=imported_total,
        excluded_missing_enquiry_time=excluded,
        by_source=dict(sorted(by_source.items())),
        by_query_type=by_query_type,
        by_date_bucket=[DateBucketCount(bucket_start=s, label=_bucket_label(s, bucket), count=per_bucket[s]) for s in bucket_starts],
        current_stage_distribution=[
            StageCount(stage=s, count=stage_counts[s], rate=round(stage_counts[s] / imported_total, 4)) for s in ordered_stages
        ],
    )
