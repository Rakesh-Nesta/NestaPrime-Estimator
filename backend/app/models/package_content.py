import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.project import Package


class PackageContent(Base):
    """Part O PACKAGES -- 'sport, tier, flooring, structure, lighting,
    scope[], warranty.' Q.1: 'Packages | Budget/Standard/Premium contents
    | Per sport | Director [edits] | Sales customises items on the
    estimate.' One row per (sport_id, tier): the Director-set DEFAULT
    content for that combination. Sales's own per-quotation
    customisation stays free text on the Estimate/Quotation itself --
    there is no EstimateOption-level override of this table.

    B.1 field #13's fuller vision -- selecting a package auto-selecting
    flooring/structure/lighting on the PROJECT itself -- needs a real
    take-off engine (Parts D/E/F) that doesn't exist in this build yet
    (see CostSheetLine's own docstring on the same gap). This table is
    read-only reference content consumed by the Estimate PDF (M.6), not
    a project-mutating side effect.

    scope_description is Director free text, one bullet per line -- not
    a reference into ScopeItem/Part I, which is the separate ADDITIONAL
    scope checklist (civil/electrical/... add-ons beyond the sport
    itself). PACKAGES describes what a tier already includes."""

    __tablename__ = "package_contents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False)
    tier: Mapped[Package] = mapped_column(Enum(Package, name="package"), nullable=False)

    flooring_description: Mapped[str] = mapped_column(Text, nullable=False)
    structure_description: Mapped[str] = mapped_column(Text, nullable=False)
    lighting_description: Mapped[str] = mapped_column(Text, nullable=False)
    scope_description: Mapped[str] = mapped_column(Text, nullable=False)
    warranty_years: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (UniqueConstraint("sport_id", "tier", name="uq_package_content_sport_tier"),)
