import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Numeric, String
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

    # M.7.2 rule 5 (DPDP Act 2023, WhatsApp policy): "each contact carries
    # whatsapp_opt_in, email_opt_in and consent_date; WhatsApp business
    # messages are sent only to opted-in numbers." No separate CONTACTS
    # table exists for vendors (Vendor is a flat single-contact record, as
    # it already was before M.7.3) so these live directly on Vendor.
    # `phone` doubles as the WhatsApp number -- the blueprint's CONTACTS
    # entity has a dedicated whatsapp_number field, but this app has never
    # modelled a vendor having two different numbers, and adding one here
    # would be new scope M.7.3 doesn't itself require. WhatsApp defaults
    # to opted-out (Meta's own policy requires affirmative opt-in);
    # ordinary business email is opt-out by nature, not opt-in, so
    # email_opt_in defaults True and is only ever flipped False by a
    # recorded opt-out.
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consent_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
