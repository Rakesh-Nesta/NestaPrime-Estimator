import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccessoryCatalogItem(Base):
    """Part I / Module 9: 'Accessories (auto per sport): goals, nets,
    posts, scoreboards, stumps, umpire chairs, lane ropes, starting
    blocks, glass doors (padel), padel nets, pickleball nets, archery
    targets.' The blueprint names the item *types* but gives no per-sport
    quantity table -- accessories.py's own ACCESSORY_CATALOG docstring
    already says this is 'this implementation's own working default' --
    so this table is that same working default, now Director-editable
    instead of a Python dict (the audit's own 'hardcoded technical
    catalogues' finding). Unlike STRUCTURE_DEFAULTS/PIPE_WEIGHT_KG_PER_M
    (E.1/E.2), which the code documents as physical/engineering standards
    NOT meant to be Master-Settings-editable, this is ordinary business
    data -- which accessory NestaPrime includes per sport, and how many
    -- exactly the kind of thing that changes as the catalogue grows.

    quantity_per_court multiplies by ProjectSport.number_of_courts at
    take-off time (accessories.py), same as the dict version did.
    is_active follows Sport/ScopeItem/Hub's own convention: deactivating
    retires an item from new take-offs without touching CostSheetLine
    rows a past take-off already created from it."""

    __tablename__ = "accessory_catalog_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_per_court: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("sport_id", "item_name", name="uq_accessory_catalog_sport_item"),)
