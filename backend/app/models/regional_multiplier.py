import uuid

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegionalMultiplier(Base):
    """Part O REGIONAL_MULTIPLIERS. Seeded per B.2's worked examples for
    Mumbai, Chennai and Delhi NCR; every other city is a neutral 1.0 [confirm]
    placeholder until the Director enters real figures (Q.3 — nothing here
    blocks development, these are editable defaults, not hard-coded facts)."""

    __tablename__ = "regional_multipliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    city: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    labour_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0, nullable=False)
    transport_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0, nullable=False)
    material_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0, nullable=False)

    climate_zone: Mapped[str] = mapped_column(String(50), default="unspecified", nullable=False)
    rainfall_zone: Mapped[str] = mapped_column(String(50), default="unspecified", nullable=False)
    coastal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wind_zone: Mapped[str] = mapped_column(String(50), default="unspecified", nullable=False)
    seismic_zone: Mapped[str] = mapped_column(String(50), default="unspecified", nullable=False)

    # E.5: coastal or wind-zone >= 4 triggers hot-dip galvanising (+15% MS) and
    # section/thickness upsize when the structure engine (Part E) is built.
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # False = still the seeded [confirm] placeholder, not Director-reviewed
