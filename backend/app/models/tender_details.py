import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
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


class TenderCompetitorBid(Base):
    """Part L 'Price basis' row: 'L1 mode shows margin at proposed price
    live.' The blueprint gives no schema for tracking competing bids --
    this is the minimum needed to make 'live' mean something: as PM/
    Director learn of other bidders' amounts during price discovery
    (a pre-bid estimate, a rumoured figure, the actual opening-day
    reading), they record it here; the L1 view (tender.py) then compares
    the project's current Quotation total against whatever's on file,
    live, rather than a one-time snapshot."""

    __tablename__ = "tender_competitor_bids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_details_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_details.id"), nullable=False
    )
    bidder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
