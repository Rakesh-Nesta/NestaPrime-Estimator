"""P3 contract (revision 4), Section 8/9: the operational screen (PM/Director only) and the
Marketing Phase A aggregate dashboard (a new, narrow, aggregates-only endpoint -- Marketing is
added to this one role gate and nowhere else)."""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
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


class StageCount(BaseModel):
    stage: str
    count: int


class MarketingDashboardOut(BaseModel):
    period_start: date
    period_end: date
    imported_total: int
    by_query_type: dict[str, int]
    current_stage_distribution: list[StageCount]


@router.get("/marketing/dashboard", response_model=MarketingDashboardOut)
def get_marketing_dashboard(
    period_start: date,
    period_end: date,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MARKETING_ROLES)),
):
    """Section 9 (revision 4, precisely redefined): a CURRENT-STAGE SNAPSHOT grouped by import
    cohort (enquiry_time in [period_start, period_end]) -- not a true historical conversion
    funnel, which would require querying Opportunity stage-change history from audit_log (not
    attempted this release). Returns counts and rates only -- never individual buyer fields,
    never raw payload, never full Opportunity rows. query_type is read from the ledger's own
    durable column (not raw_payload), so this keeps working after the 90-day retention purge."""
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    ledger_rows = (
        db.query(MarketplaceLeadImport)
        .filter(MarketplaceLeadImport.enquiry_time.isnot(None))
        .filter(MarketplaceLeadImport.enquiry_time >= period_start_dt, MarketplaceLeadImport.enquiry_time <= period_end_dt)
        .all()
    )
    by_query_type: dict[str, int] = {}
    for row in ledger_rows:
        key = row.query_type or "unknown"
        by_query_type[key] = by_query_type.get(key, 0) + 1

    opportunity_ids = [row.opportunity_id for row in ledger_rows if row.opportunity_id is not None]
    stage_counts: dict[str, int] = {}
    if opportunity_ids:
        rows = (
            db.query(Opportunity.stage, func.count(Opportunity.id))
            .filter(Opportunity.id.in_(opportunity_ids))
            .group_by(Opportunity.stage)
            .all()
        )
        for stage, count in rows:
            stage_value = stage.value if isinstance(stage, OpportunityStage) else stage
            stage_counts[stage_value] = count

    return MarketingDashboardOut(
        period_start=period_start,
        period_end=period_end,
        imported_total=len(ledger_rows),
        by_query_type=by_query_type,
        current_stage_distribution=[StageCount(stage=k, count=v) for k, v in sorted(stage_counts.items())],
    )
