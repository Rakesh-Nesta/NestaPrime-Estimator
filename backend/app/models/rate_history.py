import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateHistory(Base):
    """Part O RATE_HISTORY: 'rate_id, rate, effective_from, effective_to,
    vendor_id, project_no, changed_by, reason (normalised, one row per
    change -- used by BI).' A row is written every time a rate_item's
    rate value changes, including its very first value at creation.
    Confirming a Manual rate into an AI rate (rate_items.py's /confirm)
    does not by itself write a row here -- the rate value doesn't change,
    only its verification status. effective_to is null for the row
    currently in force; the previous row's effective_to is closed off
    (set to one day before the new row's effective_from) when a new rate
    is recorded, so the two never overlap."""

    __tablename__ = "rate_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rate_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rate_items.id"), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Optional context for BI (Part O): which vendor quoted this rate and
    # which project's need prompted recording it. Neither is required --
    # a great many rate changes are simple re-quotes with no single
    # attributable project.
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)

    changed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
