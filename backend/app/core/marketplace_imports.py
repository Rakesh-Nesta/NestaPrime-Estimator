"""P3 contract (revision 4), Section 2/5: the IndiaMART import ledger's own Capture/Process/
retry/retention pipeline. Fixture-based -- nothing here makes an outbound HTTP call; the Pull
adapter (marketplace_pull.py) is the only caller that ever will, and only it touches the shared
rate gate for that purpose.

Two separate transactions per lead, never one (Section 2): Capture inserts a durable row and
commits on its own, before any mapping/validation runs; Process (a separate pass, row-locked)
maps fields and creates the real Opportunity/FollowUp in one transaction with a single final
commit. A Process failure rolls back that transaction only, then records the failure in a THIRD,
separate transaction (revision 4 fix) so the failure itself survives the rollback that caused it.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import follow_up_sync
from app.core.security import hash_password
from app.models.follow_up import FollowUpEntityType
from app.models.marketplace_lead_import import (
    MarketplaceApiRateGate,
    MarketplaceLeadImport,
    MarketplaceLeadImportDuplicateDelivery,
    MarketplaceLeadImportStatus,
    MarketplacePullCheckpoint,
)
from app.models.opportunity import Opportunity
from app.models.user import User, UserRole

PLATFORM_INDIAMART = "indiamart"
RECEIVED_VIA_PULL = "pull"

REJECTION_REASON_MAX_LEN = 500


def _utc_naive(dt: datetime) -> datetime:
    """Every DateTime column in this codebase is stored without a timezone (naive UTC
    wall-clock) -- Postgres itself strips any tzinfo on round-trip, so a caller-supplied
    tz-aware `now` must be normalized the same way before it's compared against or written
    alongside a value already read back from the database, or Python raises on the subtraction."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

# Section 2: "A capped automatic retry count (proposed: 5) moves a row to rejected."
AUTOMATIC_RETRY_CAP = 5

# Section 2 (revision 4): anchored to received_at, never enquiry_time -- see the contract's own
# "backfilled old lead" worked example for why the other anchor would purge data before it's used.
RETENTION_DAYS = 90

# Section 3: "Minimum 5 minutes between calls" -- the one shared gate every caller acquires.
RATE_GATE_MIN_INTERVAL = timedelta(minutes=5)

# Section 5: "a dedicated, non-interactive system User row ... used for both created_by_id and
# follow_up_sync's own actor attribution." is_active=False so it can never authenticate even if
# someone learned its email -- the hashed_password is a random value nobody was ever given.
SYSTEM_IMPORT_USER_EMAIL = "system-indiamart-import@nestaprime.local"

TERMINAL_LEDGER_STATUSES_ELIGIBLE_FOR_EXPIRY = (
    MarketplaceLeadImportStatus.PENDING,
    MarketplaceLeadImportStatus.QUARANTINED,
    MarketplaceLeadImportStatus.REJECTED,
)


class ProcessAttemptFailed(Exception):
    """Raised by _attempt_process on any mapping/creation failure. Caught by both process_one
    (automatic path) and manual_retry (synchronous manual path) so each can apply its own
    transaction-boundary/persistence rule around the same underlying attempt logic."""


def get_or_create_system_import_user(db: Session) -> User:
    user = db.query(User).filter(User.email == SYSTEM_IMPORT_USER_EMAIL).first()
    if user is not None:
        return user
    user = User(
        name="IndiaMART Import (system)",
        email=SYSTEM_IMPORT_USER_EMAIL,
        hashed_password=hash_password(uuid.uuid4().hex),
        role=UserRole.ADMIN,
        is_active=False,
    )
    db.add(user)
    db.flush()
    return user


# --- Section 3's shared rate gate -----------------------------------------------------------


def try_acquire_rate_gate(db: Session, *, platform: str = PLATFORM_INDIAMART, now: datetime | None = None) -> bool:
    """Acquired before any outbound HTTP request fires (Section 3), by every one of the three
    callers (scheduled Pull, each backfill chunk, "Verify key now"). Commits internally -- this
    is a small, atomic claim, not part of a caller's larger unit of work, so the timestamp is
    durable and the row lock releases immediately regardless of what the caller does next."""
    now = _utc_naive(now or datetime.now(UTC))
    row = db.execute(
        select(MarketplaceApiRateGate).where(MarketplaceApiRateGate.platform == platform).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = MarketplaceApiRateGate(platform=platform, last_call_at=None)
        db.add(row)
        db.flush()
    if row.last_call_at is not None and now - row.last_call_at < RATE_GATE_MIN_INTERVAL:
        db.commit()
        return False
    row.last_call_at = now
    db.commit()
    return True


# --- Section 2's Capture step ----------------------------------------------------------------


def _parse_enquiry_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    for parser in (
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
        lambda s: datetime.strptime(s, "%d-%b-%Y %H:%M:%S"),
        lambda s: datetime.strptime(s, "%d-%m-%Y %H:%M:%S"),
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def _extract_identity(item: dict) -> tuple[str | None, datetime | None]:
    """Structural extraction only (Section 2, revision 4) -- never full field validation. Either
    piece missing/unparseable routes this item to quarantine, not to a dropped or blocked item."""
    external_id = item.get("UNIQUE_QUERY_ID")
    external_id = external_id.strip() if isinstance(external_id, str) and external_id.strip() else None
    enquiry_time = _parse_enquiry_time(item.get("QUERY_TIME"))
    return external_id, enquiry_time


def _extract_durable_fields(item: dict) -> dict:
    return {
        "sender_company": item.get("SENDER_COMPANY") or None,
        "sender_address": item.get("SENDER_ADDRESS") or None,
        "sender_city": item.get("SENDER_CITY") or None,
        "sender_state": item.get("SENDER_STATE") or None,
        "sender_pincode": item.get("SENDER_PINCODE") or None,
        "sender_country_iso": item.get("SENDER_COUNTRY_ISO") or None,
        "query_type": item.get("QUERY_TYPE") or None,
    }


@dataclass
class CaptureResult:
    captured_ids: list[uuid.UUID] = field(default_factory=list)
    quarantined_ids: list[uuid.UUID] = field(default_factory=list)
    duplicate_of_ids: list[uuid.UUID] = field(default_factory=list)


def capture_batch(
    db: Session,
    *,
    items: list[dict],
    account_id: str,
    platform: str = PLATFORM_INDIAMART,
    received_via: str = RECEIVED_VIA_PULL,
) -> CaptureResult:
    """Section 2's Capture transaction. Every item in `items` durably lands as either a new
    `pending`/`quarantined` row or a duplicate_delivery event against an existing row -- one item
    failing (e.g. a repeat delivery) never blocks another item in the same batch, via a per-item
    SAVEPOINT (`db.begin_nested()`), and the whole batch commits once at the end as a single unit
    (matching the checkpoint rule's own "every lead in that window" requirement, Section 3)."""
    result = CaptureResult()
    for item in items:
        external_id, enquiry_time = _extract_identity(item)
        is_quarantined = external_id is None or enquiry_time is None
        row = MarketplaceLeadImport(
            platform=platform,
            account_id=account_id,
            external_id=external_id,
            enquiry_time=enquiry_time,
            received_via=received_via,
            raw_payload=item,
            status=MarketplaceLeadImportStatus.QUARANTINED if is_quarantined else MarketplaceLeadImportStatus.PENDING,
        )
        if is_quarantined:
            # Never reaches Process, so extract whatever durable fields are available now --
            # Section 2's own "or, for a quarantined row, whatever could be extracted."
            for k, v in _extract_durable_fields(item).items():
                setattr(row, k, v)

        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            # Only reachable when external_id is not None (quarantined rows are exempt from the
            # unique constraint, Section 2) -- an existing row with this identity already exists.
            existing = (
                db.query(MarketplaceLeadImport)
                .filter(
                    MarketplaceLeadImport.platform == platform,
                    MarketplaceLeadImport.account_id == account_id,
                    MarketplaceLeadImport.external_id == external_id,
                )
                .one()
            )
            _record_duplicate_delivery(db, existing.id)
            result.duplicate_of_ids.append(existing.id)
            continue

        if is_quarantined:
            result.quarantined_ids.append(row.id)
        else:
            result.captured_ids.append(row.id)

    db.commit()
    return result


def _record_duplicate_delivery(db: Session, ledger_row_id: uuid.UUID) -> None:
    log = db.get(MarketplaceLeadImportDuplicateDelivery, ledger_row_id)
    if log is None:
        db.add(MarketplaceLeadImportDuplicateDelivery(ledger_row_id=ledger_row_id, delivery_count=1))
    else:
        log.delivery_count += 1
        log.last_seen_at = datetime.now(UTC)
    db.flush()


# --- Section 5's field mapping ----------------------------------------------------------------


def _map_opportunity_fields(item: dict) -> dict:
    message_parts = [
        part for part in (item.get("QUERY_MESSAGE"), item.get("QUERY_PRODUCT_NAME"), item.get("SUBJECT")) if part
    ]
    return {
        "lead_name": item.get("SENDER_NAME") or "IndiaMART Buyer",
        "lead_phone": item.get("SENDER_MOBILE") or None,
        "lead_email": item.get("SENDER_EMAIL") or None,
        "notes": "\n".join(message_parts) if message_parts else None,
        "source": "indiamart",
    }


class ProcessSkippedWritesLocked(Exception):
    """Not a failure -- follow_up_writes_locked(db) is on (WP5 containment), matching every other
    follow-up-writing route's own guard. retry_count/rejection_reason are left untouched; the row
    stays pending and is picked up again by the next Process pass once writes are unlocked."""


def _attempt_process(db: Session, row: MarketplaceLeadImport, *, manual_by: User | None = None) -> uuid.UUID:
    """The one shared mapping/creation attempt both process_one and manual_retry use. Raises
    ProcessAttemptFailed (or lets ProcessSkippedWritesLocked propagate) on failure; the caller
    decides the transaction/persistence handling around it. Returns the new Opportunity's id."""
    if follow_up_sync.follow_up_writes_locked(db):
        raise ProcessSkippedWritesLocked()

    try:
        system_user = get_or_create_system_import_user(db)
        fields = _map_opportunity_fields(row.raw_payload or {})
        opportunity = Opportunity(
            **fields,
            created_by_id=system_user.id,
            owner_id=None,  # Section 7: lands in the unassigned queue (owner_id IS NULL AND source='indiamart')
        )
        db.add(opportunity)
        db.flush()
        follow_up_sync.set_primary_follow_up(
            db,
            opportunity,
            FollowUpEntityType.OPPORTUNITY,
            due_date=row.received_at.date(),  # Section 5: due on the import (Capture) date, decided in revision 3
            note=None,
            current_user=manual_by or system_user,
        )
        for k, v in _extract_durable_fields(row.raw_payload or {}).items():
            if getattr(row, k) is None:
                setattr(row, k, v)
        row.status = MarketplaceLeadImportStatus.CONVERTED
        row.opportunity_id = opportunity.id
        db.flush()
        return opportunity.id
    except ProcessSkippedWritesLocked:
        raise
    except Exception as exc:  # noqa: BLE001 -- any mapping/creation failure is a retryable Process failure
        raise ProcessAttemptFailed(str(exc)) from exc


@dataclass
class ProcessOutcome:
    ledger_row_id: uuid.UUID
    converted: bool
    opportunity_id: uuid.UUID | None = None
    rejection_reason: str | None = None
    status: str = MarketplaceLeadImportStatus.CONVERTED


def process_one(db: Session, *, platform: str = PLATFORM_INDIAMART) -> ProcessOutcome | None:
    """Section 2's Process step: claims exactly one `pending` row via
    `SELECT ... FOR UPDATE SKIP LOCKED`, attempts the real Opportunity/FollowUp creation in one
    transaction with a single final commit, and on failure rolls that back before recording the
    failure in a separate transaction (revision 4 fix -- see module docstring). Returns None when
    there is nothing pending to process (not an error)."""
    row = db.execute(
        select(MarketplaceLeadImport)
        .where(MarketplaceLeadImport.platform == platform, MarketplaceLeadImport.status == MarketplaceLeadImportStatus.PENDING)
        .order_by(MarketplaceLeadImport.received_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if row is None:
        return None

    row_id = row.id
    try:
        opportunity_id = _attempt_process(db, row)
        db.commit()
        return ProcessOutcome(ledger_row_id=row_id, converted=True, opportunity_id=opportunity_id)
    except ProcessSkippedWritesLocked:
        db.rollback()
        return None
    except ProcessAttemptFailed as exc:
        db.rollback()
        # Third, separate transaction (revision 4 fix): the failure must survive the rollback
        # that caused it, or automatic-retry history becomes silently unobservable.
        failed_row = db.get(MarketplaceLeadImport, row_id)
        failed_row.retry_count += 1
        failed_row.rejection_reason = str(exc)[:REJECTION_REASON_MAX_LEN]
        if failed_row.retry_count >= AUTOMATIC_RETRY_CAP:
            failed_row.status = MarketplaceLeadImportStatus.REJECTED
        db.commit()
        return ProcessOutcome(
            ledger_row_id=row_id,
            converted=False,
            rejection_reason=failed_row.rejection_reason,
            status=failed_row.status,
        )


@dataclass
class ManualRetryOutcome:
    ledger_row_id: uuid.UUID
    converted: bool
    opportunity_id: uuid.UUID | None = None
    rejection_reason: str | None = None


def manual_retry(db: Session, *, ledger_row_id: uuid.UUID, current_user: User) -> ManualRetryOutcome:
    """Section 2 (revision 4 fix): synchronously attempts real processing right now, in the same
    request -- never just a status flip. Never blocked by AUTOMATIC_RETRY_CAP (that cap governs
    only unattended system behaviour) and never touches retry_count itself, preserving the
    automatic-attempt history that led to the rejection."""
    row = db.execute(
        select(MarketplaceLeadImport).where(MarketplaceLeadImport.id == ledger_row_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("Import row not found")
    if row.status != MarketplaceLeadImportStatus.REJECTED:
        raise ValueError(f"Only a rejected row can be manually retried (status is {row.status})")

    now = _utc_naive(datetime.now(UTC))
    try:
        opportunity_id = _attempt_process(db, row, manual_by=current_user)
        row.manually_retried_at = now
        row.manually_retried_by_id = current_user.id
        db.commit()
        return ManualRetryOutcome(ledger_row_id=row.id, converted=True, opportunity_id=opportunity_id)
    except ProcessAttemptFailed as exc:
        db.rollback()
        failed_row = db.get(MarketplaceLeadImport, ledger_row_id)
        failed_row.rejection_reason = str(exc)[:REJECTION_REASON_MAX_LEN]  # a NEW reason, distinguishable from the prior one
        failed_row.status = MarketplaceLeadImportStatus.REJECTED
        failed_row.manually_retried_at = now
        failed_row.manually_retried_by_id = current_user.id
        db.commit()
        return ManualRetryOutcome(ledger_row_id=ledger_row_id, converted=False, rejection_reason=failed_row.rejection_reason)


# --- Section 2's retention/expiry -------------------------------------------------------------


@dataclass
class RetentionResult:
    purged_ids: list[uuid.UUID] = field(default_factory=list)
    expired_ids: list[uuid.UUID] = field(default_factory=list)


def run_retention_purge(
    db: Session, *, platform: str = PLATFORM_INDIAMART, retention_days: int = RETENTION_DAYS, now: datetime | None = None
) -> RetentionResult:
    """Section 2 (revision 4 fix): anchored to received_at, never enquiry_time. Nulls the entire
    raw_payload for any row past its window (not selected fields -- QUERY_MESSAGE free text can
    itself carry PII); a still-pending/quarantined/rejected row past its window also transitions
    to the new terminal `expired` status in the same pass, distinct from `rejected` so no Retry
    action is ever offered for it (the payload a retry needs no longer exists)."""
    now = _utc_naive(now or datetime.now(UTC))
    cutoff = now - timedelta(days=retention_days)
    result = RetentionResult()

    rows = (
        db.query(MarketplaceLeadImport)
        .filter(MarketplaceLeadImport.platform == platform, MarketplaceLeadImport.received_at <= cutoff)
        .filter(MarketplaceLeadImport.raw_payload.isnot(None))
        .all()
    )
    for row in rows:
        row.raw_payload = None
        result.purged_ids.append(row.id)
        if row.status in TERMINAL_LEDGER_STATUSES_ELIGIBLE_FOR_EXPIRY:
            row.status = MarketplaceLeadImportStatus.EXPIRED
            result.expired_ids.append(row.id)

    db.commit()
    return result


# --- Section 3's checkpoint ---------------------------------------------------------------------


def get_checkpoint(db: Session, *, platform: str = PLATFORM_INDIAMART) -> datetime | None:
    row = db.get(MarketplacePullCheckpoint, platform)
    return row.last_captured_end_time if row else None


def advance_checkpoint(db: Session, *, platform: str = PLATFORM_INDIAMART, end_time: datetime) -> None:
    """Section 3: advances only after every lead in that window has a durably committed Capture
    row -- callers must call this only after capture_batch's own commit has already succeeded."""
    row = db.get(MarketplacePullCheckpoint, platform)
    if row is None:
        row = MarketplacePullCheckpoint(platform=platform, last_captured_end_time=end_time)
        db.add(row)
    else:
        row.last_captured_end_time = end_time
    db.commit()
