import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Vendor(Base):
    """Part O VENDOR_MASTER: 'name, city, category, contact, gstin (null =
    unregistered -> no ITC flag), rcm_applicable, payment_terms (printed
    on PO), reliability_score (from delivery-date variance in
    PROJECT_ACTUALS; shown on RFQ vendor pick) (rates in RATE_HISTORY).'

    reliability_score has no automatic source yet -- PROJECT_ACTUALS
    (Module 15) is explicitly Roadmap Phase 6, not built -- so it is a
    plain nullable field a PM/Director can set manually, not something
    this app computes."""

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Informational only, same K.1b/K.4 stance as CLIENTS.gstin -- never
    # used to compute anything, just null = unregistered -> no ITC flag.
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    rcm_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
