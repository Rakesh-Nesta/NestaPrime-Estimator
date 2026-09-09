import uuid

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NettingGrade(Base):
    """E.3: 'Netting grades' -- N1 Budget / N2 Standard / N3 Heavy / N4
    Welded mesh, each with its own material/twine/mesh/UV spec and a
    starting Rs/sqm range [confirm]. Before this table, add_structure_takeoff
    (structures.py) only accepted a bare PM-entered netting_rate_per_sqm --
    functional, but not the catalogue E.3 actually describes (the audit's
    ranked gap #12). rate_per_sqm is the single current Director-editable
    figure standing in for the blueprint's range (same "one number, not a
    range, once NestaPrime commits to a figure" pattern as every other
    [confirm] rate in this codebase). Grade selection is optional on the
    take-off -- a PM can still enter a bare rate for a one-off spec the
    catalogue doesn't cover, same as the accessory catalog's own custom_items
    escape hatch. is_active follows Sport/ScopeItem/Hub/AccessoryCatalogItem's
    convention: deactivating retires a grade from new take-offs without
    touching CostSheetLine rows a past take-off already created from it."""

    __tablename__ = "netting_grades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    material: Mapped[str] = mapped_column(String(50), nullable=False)
    twine: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mesh: Mapped[str] = mapped_column(String(30), nullable=False)
    uv_stabilized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = "--" (N4: not applicable)
    typical_use: Mapped[str] = mapped_column(String(150), nullable=False)
    rate_per_sqm: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("key", name="uq_netting_grade_key"),)
