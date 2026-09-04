import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScopeItemGroup(str, enum.Enum):
    CIVIL = "civil"
    ELECTRICAL = "electrical"
    WATER = "water"
    EXTERNAL = "external"
    SERVICES = "services"
    MAINTENANCE = "maintenance"


class ScopeItem(Base):
    """Part I — Additional Scope Checklist (Module 10), 30 items across six
    groups. Reference data, seeded once (see app/seed_data.py) and
    read-only via the API in Phase 1b."""

    __tablename__ = "scope_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    group: Mapped[ScopeItemGroup] = mapped_column(
        Enum(ScopeItemGroup, name="scope_item_group"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)


class ProjectScopeItem(Base):
    """A scope item explicitly included on a project (Module 10 output).
    Part I: 'unchecked = excluded and listed under Exclusions' — so only
    included items are stored here; anything without a row is implicitly
    excluded, rather than persisting an included=False row for the other 29."""

    __tablename__ = "project_scope_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    scope_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scope_items.id"), nullable=False
    )
    # Free-text extra detail where the checklist item needs it, e.g.
    # "pavilion/gallery + seating count" -> note="200 seats".
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
