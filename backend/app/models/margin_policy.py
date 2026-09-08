import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.client import ClientType


class MarginPolicy(Base):
    """K.2 — margin floor and target per client type. 'Floor margin is the
    minimum below which Director approval is needed'; 'Target margin ...
    is what the system prices with' and is derived from the floor: target =
    floor + (competitive_segment ? 3 : 5) points. Reference data (seeded
    with K.2's own defaults), editable later by the Director in Master
    Settings (Q.1). K.2 also defines a sport-type floor override that
    REPLACES this client floor for a given sport (see SportMarginPolicy
    below) and a cost-weighted-average rule for multi-sport projects --
    both implemented in pricing.py, not deferred."""

    __tablename__ = "margin_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_type: Mapped[ClientType] = mapped_column(
        Enum(ClientType, name="client_type"), unique=True, nullable=False
    )
    floor_margin_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # Per-client-type Master Setting (K.2): drives the +3 vs +5 point gap
    # between floor and target margin. K.2 defines this flag as
    # client-type-scoped only -- there is no sport-level equivalent
    # anywhere in the blueprint, so a sport-type floor override (below)
    # still uses the CLIENT's own competitive_segment gap; only the
    # floor itself is replaced.
    competitive_segment: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SportMarginPolicy(Base):
    """K.2: 'A sport-type floor (e.g. Pool 15%, PEB 14%) replaces the
    client floor for that sport when the Director has defined one
    (large-ticket jobs are allowed a lower floor).' One row per sport,
    Director-set; a sport with no row here simply uses its project's
    client-type floor (MarginPolicy), unchanged from the base behaviour.
    No sport is seeded with a default here -- K.2's 'Pool 15%, PEB 14%'
    are given as illustrative examples ('e.g.'), not firm blueprint
    defaults, so nothing is fabricated for any specific sport."""

    __tablename__ = "sport_margin_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sports.id"), unique=True, nullable=False
    )
    floor_margin_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
