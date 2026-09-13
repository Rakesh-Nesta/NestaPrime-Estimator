import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AddonCategory(str, enum.Enum):
    LIGHTING = "lighting"
    FENCING = "fencing"
    SEATING = "seating"
    AMC = "amc"
    OTHER = "other"


class CrossSellAddon(Base):
    """Amendment 3 (Annexure 2): "Complete Your Facility" -- suggest
    sport-matched add-ons at the Estimate step, with their own price and
    margin. Selling price is computed from cost + margin_percent the same
    way K.2 computes every other selling price in this app (never a flat
    typed-in client price), so a margin change stays auditable the same
    way rate/margin changes are everywhere else.

    cost/margin_percent are nullable and is_active defaults False: an
    add-on category with no defensible real-world price (per Note R1's
    own discipline -- Lighting/Seating/AMC had no usable reference data
    when this shipped) is still a real, sport-tagged catalog row, just
    kept inactive (hidden from the Estimate step) until a PM/Director
    enters a real cost, rather than fabricated for a client-facing
    document. all_sports lets one row (e.g. AMC) match every project
    without needing a row in cross_sell_addon_sports per sport."""

    __tablename__ = "cross_sell_addons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[AddonCategory] = mapped_column(Enum(AddonCategory, name="addon_category"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Nullable, e.g. "sqft"/"rft" for a real per-unit rate (Fencing) vs a
    # flat per-job price (AMC) -- whichever the underlying reference data
    # actually is, rather than assuming a fixed package size to force a
    # single total.
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    margin_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    all_sports: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class CrossSellAddonSport(Base):
    """One row per (addon, sport) it's suggested for -- not consulted at
    all when the addon's own all_sports flag is set."""

    __tablename__ = "cross_sell_addon_sports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    addon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cross_sell_addons.id"), nullable=False)
    sport_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False)
