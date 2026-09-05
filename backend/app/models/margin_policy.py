import uuid

from sqlalchemy import Boolean, Enum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.client import ClientType


class MarginPolicy(Base):
    """K.2 — margin floor and target per client type. 'Floor margin is the
    minimum below which Director approval is needed'; 'Target margin ...
    is what the system prices with' and is derived from the floor: target =
    floor + (competitive_segment ? 3 : 5) points. Reference data (seeded
    with K.2's own defaults) editable later by the Director in Master
    Settings (Q.1) — Phase 1b has no sport-type override or multi-sport
    cost-weighted-average yet, both deferred until a real per-project cost
    breakdown exists to weight."""

    __tablename__ = "margin_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_type: Mapped[ClientType] = mapped_column(
        Enum(ClientType, name="client_type"), unique=True, nullable=False
    )
    floor_margin_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # Per-client-type Master Setting (K.2): drives the +3 vs +5 point gap
    # between floor and target margin.
    competitive_segment: Mapped[bool] = mapped_column(Boolean, nullable=False)
