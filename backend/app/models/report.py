import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportType(str, enum.Enum):
    PIPELINE = "pipeline"
    MARGIN = "margin"


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    RELEASED = "released"


class Report(Base):
    """Part T (Module 21). 'Every report is a computed snapshot of existing
    tables ... reporting introduces no new source of truth' -- content is
    computed at generation time from Estimate/Quotation/CostSheet/Override
    and frozen into this row with a SHA-256 hash (same integrity pattern as
    ATTACHMENTS, M.3). Re-running the same period later inserts a NEW row
    rather than editing this one (T.2 rule 2), so a report can always be
    shown unchanged in a later dispute."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type"), nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    source_tables: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # T.2 rule 4: a report reaching Director/CA-only content (Margin) is
    # Draft until the Director marks it Released, mirroring the Cost
    # Sheet's verification gate. Pipeline carries nothing Sales doesn't
    # already see on the documents themselves, so it is Released immediately
    # on generation -- there is nothing to gate.
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), default=ReportStatus.DRAFT, nullable=False
    )

    generated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    released_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
