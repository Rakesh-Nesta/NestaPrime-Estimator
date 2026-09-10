import uuid

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VehicleClass(Base):
    """Q.1: 'Freight & crane | Rs/km by vehicle class, truck capacity t,
    crane day rate | Global | Director | PM on the Cost Sheet.' The
    blueprint gives no worked example for this row -- no vehicle names,
    capacities or Rs/km figures anywhere in the document, unlike E.3's
    netting grades or B.2's warranty years -- so this table starts empty
    (same as HUBS) rather than seeded with invented numbers; NestaPrime
    adds its own actual fleet/vendor vehicle classes.

    Selecting one on the freight take-off (overheads.py) both supplies
    rate_per_km and, combined with a PM-entered total_material_tonnes,
    lets trips = ceil(tonnes / truck_capacity_tonnes) be computed
    automatically -- B.1's own formula -- rather than PM-guessed. is_active
    follows this codebase's usual convention: deactivating retires a class
    from new take-offs without touching CostSheetLine rows a past
    take-off already created from it."""

    __tablename__ = "vehicle_classes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    truck_capacity_tonnes: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    rate_per_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("key", name="uq_vehicle_class_key"),)
