import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Hub(Base):
    """Part O HUBS -- 'hub name, city, state_code (distance km is entered
    by the PM or computed from PIN via a mapping API in Phase 7; Phase 1
    = manual km).' B.1 field #4 ('Distance from nearest NestaPrime hub')
    needs a hub to measure FROM -- this is that Director-managed master
    list of NestaPrime's own dispatch/depot locations. Project.hub_id
    records which hub the PM measured from; Project.distance_km stays
    the manual km entry itself (M.4a item 5) until the Phase 7 PIN-to-km
    integration lands, same pattern as CostSheetLine deferring the
    take-off engine.

    is_active follows Sport/ScopeItem's own convention: deactivating
    retires a hub from new selection without breaking any project that
    already references it."""

    __tablename__ = "hubs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state_code: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
