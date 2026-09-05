import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenderDetails(Base):
    """Part L — Tender Mode (Government clients), one row per project.
    Covers the tracking fields (EMD, retention, BG %, DLP, key dates) that
    don't need a real Cost Sheet/line-item structure to exist yet. The
    BOQ-style itemised format, statutory cess/TDS placement in K.1, and
    post-award tracking all need infrastructure (Part M documents, a real
    take-off) that isn't built yet — deliberately not modelled here."""

    __tablename__ = "tender_details"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), unique=True, nullable=False
    )

    emd_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    emd_validity_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # L: "Security deposit / retention: 5-10% [confirm] withheld -> shown
    # in net receivable."
    retention_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # L: "Performance bank guarantee: 3-5% of contract."
    performance_bg_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # L: "Defect-liability period: 12 months default."
    dlp_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)

    bid_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pre_bid_meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opening_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
