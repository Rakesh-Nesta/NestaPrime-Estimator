"""WP5 (correction plan, 2026-09-27): one shared follow-up model instead of each record type
carrying its own copy of next_follow_up_date/follow_up_note. A FollowUp is polymorphic --
entity_type + entity_id name the record it belongs to (Client, Opportunity, Project, Site
Survey, Cost Sheet, Estimate, Quotation, Price Request, Payment Milestone, Work Order) --
rather than a foreign key per record type, since no single column could reference ten
different tables at once. Permission and ownership are never decided independently here:
app/core/follow_up_entities.py resolves each entity_type back to the exact read/write role
check and owner_id that entity's own existing screen already uses, so a Sales rep sees the
same follow-ups on this table as the records they can already open elsewhere."""

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FollowUpEntityType(str, enum.Enum):
    CLIENT = "client"
    OPPORTUNITY = "opportunity"
    PROJECT = "project"
    SITE_SURVEY = "site_survey"
    COST_SHEET = "cost_sheet"
    ESTIMATE = "estimate"
    QUOTATION = "quotation"
    PRICE_REQUEST = "price_request"
    PAYMENT_MILESTONE = "payment_milestone"
    WORK_ORDER = "work_order"


class FollowUpStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


TERMINAL_FOLLOW_UP_STATUSES = (FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED)


class WaitingParty(str, enum.Enum):
    US = "us"
    CLIENT = "client"
    VENDOR = "vendor"


class FollowUp(Base):
    """Multiple OPEN follow-ups on one record are allowed on purpose (a routine call-back
    and a specialist site-visit can coexist) -- purpose_key is what stops a duplicate, and
    only for automated actions that carry one; a manually created follow-up has none and is
    never deduplicated against another manual one."""

    __tablename__ = "follow_ups"
    __table_args__ = (
        # Prevents a duplicate OPEN automated action (same entity + purpose_key) --
        # NOT a one-follow-up-per-record limit; a manual follow-up (purpose_key IS NULL)
        # is never deduplicated by this index. The application also checks for an
        # existing row before inserting (belt), but this index is the actual guarantee
        # under a genuine race between two concurrent identical requests (braces) -- the
        # API's IntegrityError handler turns a race loss into the same 201/idempotent
        # response as the normal check-first path, not a 500.
        #
        # Root cause of an earlier broken version of this index, for the record: Postgres
        # enum columns created by SQLAlchemy store the Python Enum's MEMBER NAME
        # ('COMPLETED'), not its .value ('completed') -- invisible everywhere else because
        # the ORM translates both directions automatically, but a raw-SQL index predicate
        # bypasses that translation. A predicate written as
        # `status NOT IN ('completed', 'cancelled')` (or explicitly cast to the enum type)
        # references labels the enum type does not actually contain, and Postgres rejects
        # the CREATE INDEX with "invalid input value for enum follow_up_status: 'completed'"
        # -- reproduced in complete isolation with a two-line unrelated model, confirming it
        # is a general SQLAlchemy/Postgres enum-DDL behaviour, not anything specific to this
        # table. Fixed by matching the true stored representation (uppercase names).
        Index(
            "uq_follow_ups_purpose_key_open",
            "entity_type", "entity_id", "purpose_key",
            unique=True,
            postgresql_where=text("purpose_key IS NOT NULL AND status NOT IN ('COMPLETED', 'CANCELLED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[FollowUpEntityType] = mapped_column(
        Enum(FollowUpEntityType, name="follow_up_entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Stable key for an automated action (e.g. "won_stage_review"); null for a manual one.
    purpose_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    # True once a person other than the entity's own current owner is deliberately assigned.
    # Reassigning the ENTITY's owner (Team & Access -> Record owners) must never silently
    # move a follow-up with this flag set -- it stays with its explicit assignee.
    owner_explicitly_assigned: Mapped[bool] = mapped_column(default=False, nullable=False)

    next_action: Mapped[str] = mapped_column(String(300), nullable=False)
    due_date: Mapped[date] = mapped_column(nullable=False)

    status: Mapped[FollowUpStatus] = mapped_column(
        Enum(FollowUpStatus, name="follow_up_status"), default=FollowUpStatus.OPEN, nullable=False
    )
    # Required (enforced in the API, not the schema) when status == WAITING.
    waiting_party: Mapped[WaitingParty | None] = mapped_column(Enum(WaitingParty, name="waiting_party"), nullable=True)
    review_date: Mapped[date | None] = mapped_column(nullable=True)

    outcome: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # overdue is deliberately NOT a column -- computed the same way Payments already does it:
    # due_date < today AND status NOT IN ('completed', 'cancelled'). Storing it would drift.


class FollowUpHistory(Base):
    """One row per change to a FollowUp's due_date, owner_id, status or next_action --
    old_value/new_value are stringified the same way AuditLogEntry already does it, so a
    reschedule's "what did it used to say" is always answerable, which the old
    overwrite-in-place columns could never provide."""

    __tablename__ = "follow_up_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follow_up_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("follow_ups.id"), nullable=False)
    changed_field: Mapped[str] = mapped_column(String(30), nullable=False)  # due_date | owner_id | status | next_action
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
