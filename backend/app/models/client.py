import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientType(str, enum.Enum):
    """B.1 field #1. Drives default package, payment-term template, margin
    floor (K.2) and warranty; Government also switches on Tender Mode (Part L)."""

    SCHOOL = "school"
    COLLEGE = "college"
    HOUSING_SOCIETY = "housing_society"
    CORPORATE = "corporate"
    CLUB = "club"
    GOVERNMENT = "government"
    INDIVIDUAL = "individual"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ClientType] = mapped_column(Enum(ClientType, name="client_type"), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Informational only per v5.1.9 K.4 — printed on the quotation if supplied,
    # never used to compute anything (the app applies no GST classification).
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)

    credit_limit: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Blocks per M.4a-adjacent rules referenced in Part O.
    overdue_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blacklist_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # M.7.2 rule 5 (DPDP Act 2023, WhatsApp policy): "each contact carries
    # whatsapp_opt_in, email_opt_in and consent_date; WhatsApp business
    # messages are sent only to opted-in numbers." No separate CONTACTS
    # table exists for clients (same simplification Vendor already uses --
    # a flat single-contact record) so these live directly on Client.
    # WhatsApp defaults to opted-out (Meta's own policy requires
    # affirmative opt-in); ordinary business email is opt-out by nature,
    # not opt-in, so email_opt_in defaults True and is only ever flipped
    # False by a recorded opt-out.
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consent_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
