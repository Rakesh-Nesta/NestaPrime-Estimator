import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SkipRequestStage(str, enum.Enum):
    """M.2 rule 3's own examples ('client wants a quotation directly, or
    an estimate without a full cost sheet') both describe the SAME
    mechanism: the Cost Sheet stage is skipped/auto-generated, which then
    unblocks creating the next stage on top of it. No separate mechanism
    for skipping the Estimate stage itself is specified anywhere in the
    blueprint (no ESTIMATES.Unverified status exists to support one), so
    COST_SHEET is the only value -- adding others would be inventing a
    workflow the blueprint doesn't describe."""

    COST_SHEET = "cost_sheet"


class SkipRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"


class SkipRequest(Base):
    """Part O: 'SKIP_REQUESTS -- document, stage skipped, requested_by,
    approved_by, reason, timestamp' (the complete field list -- no status
    or rejection field is named, but a pending/approved status is the
    minimum needed to track the M.4 approval-matrix distinction between
    Sales, who can only request, and PM/Director, who can approve). M.2
    rule 3: 'Sales cannot skip alone' -- approving one here creates the
    auto-generated CostSheet (status Unverified, auto_generated=True).
    'document' is the project this skip applies to; there is no document
    to reference yet since the skipped stage is exactly what doesn't
    exist until the request is approved."""

    __tablename__ = "skip_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    stage_skipped: Mapped[SkipRequestStage] = mapped_column(
        Enum(SkipRequestStage, name="skip_request_stage"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[SkipRequestStatus] = mapped_column(
        Enum(SkipRequestStatus, name="skip_request_status"), default=SkipRequestStatus.PENDING, nullable=False
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resulting_cost_sheet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_sheets.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
