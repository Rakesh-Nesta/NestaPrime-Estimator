import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReadinessDocumentType(str, enum.Enum):
    ESTIMATE = "estimate"
    QUOTATION = "quotation"


class ReadinessCheckKey(str, enum.Enum):
    """WP7 (correction plan, 2026-09-28): the three WAIVABLE readiness checks -- Cost
    Sheet not Verified and below-floor margin are already separate, pre-existing hard/
    Director-only gates in release_quotation and mark_quotation_won and are untouched by
    this mechanism; the new client-identity check is a hard, non-waivable block and has
    no exception path at all."""

    SITE_SURVEY = "site_survey"
    SCOPE = "scope"
    SPORT = "sport"


class ReadinessExceptionStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReadinessException(Base):
    """WP7 (correction plan, 2026-09-28): mirrors SkipRequest's own proven PM-requests,
    Director-approves-or-rejects shape (app/models/skip_request.py), generalised from
    Cost Sheet skipping to the three waivable readiness checks -- a Director recording
    one directly is the same POST as a PM's request, just auto-approved based on the
    caller's own role (see app/api/readiness.py's create_readiness_exception), not a
    separate code path or model state here.

    Scoped to one exact (document_type, document_id) -- a specific Estimate or Quotation
    row, never the Project generally. Revising a document (WP4's established pattern:
    a new revision is a new row with a new id) means a fresh document_id, so a prior
    exception never silently carries over -- exactly the "a later revision does not
    inherit it" rule the design calls for, with no extra field needed for it."""

    __tablename__ = "readiness_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_type: Mapped[ReadinessDocumentType] = mapped_column(
        Enum(ReadinessDocumentType, name="readiness_document_type"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    check_key: Mapped[ReadinessCheckKey] = mapped_column(
        Enum(ReadinessCheckKey, name="readiness_check_key"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ReadinessExceptionStatus] = mapped_column(
        Enum(ReadinessExceptionStatus, name="readiness_exception_status"),
        default=ReadinessExceptionStatus.REQUESTED, nullable=False,
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Amendment 33's own SkipRequest precedent: separate from `reason` above (the
    # requester's own justification), never overwriting it.
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
