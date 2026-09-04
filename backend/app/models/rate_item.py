import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateSource(str, enum.Enum):
    AI = "ai"
    MANUAL = "manual"


class LabourCategory(Base):
    """J.2 — activity-rate-card categories with their fallback %, used
    "only when an item has none" (J.1). Reference data, seeded once (see
    app/seed_data.py)."""

    __tablename__ = "labour_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class RateItem(Base):
    """J.1 — Rate sheet (Module 11). Every entry starts life as a Manual,
    unverified rate; a PM or Director confirming it is what promotes it to
    an AI (master) rate — 'Unverified rates never become defaults.'"""

    __tablename__ = "rate_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(300), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    hsn_sac: Mapped[str] = mapped_column(String(20), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    source: Mapped[RateSource] = mapped_column(
        Enum(RateSource, name="rate_source"), default=RateSource.MANUAL, nullable=False
    )
    # Unverified manual rates never become defaults (J.1); an AI rate is
    # always verified by definition (it only becomes AI via confirmation).
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vendor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    confirmed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Only meaningful for source=manual — "used as entered (it is already
    # local)", not adjusted by regional multipliers like AI/master rates.
    city_of_quote: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # "the blended 22% is used only when an item has none" (J.1) — so this
    # is nullable, not a required FK.
    labour_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("labour_categories.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
