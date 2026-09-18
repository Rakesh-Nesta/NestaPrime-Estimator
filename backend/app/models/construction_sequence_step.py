import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConstructionPhase(str, enum.Enum):
    """Section 18 (Amendment 16, Part 2): six fixed phases, matching the
    Director's own scenario wording almost verbatim ("base, flooring,
    lighting, pole, ring... all things and process") -- fixed rather than
    free-form so every sport's sequence is comparable, per the approved
    spec's Decision 1."""

    SITE_PREP = "site_prep"
    SUB_BASE = "sub_base"
    FLOORING = "flooring"
    STRUCTURE_FIXTURES = "structure_fixtures"
    LIGHTING = "lighting"
    ACCESSORIES_FINISHING = "accessories_finishing"


class ConstructionSequenceStep(Base):
    """Section 18 -- Amendment 16 Part 2. Unlike the rest of the Build
    Guide (FlooringGuide/AccessoryCatalogItem/PackageContent), this is
    genuinely new content that doesn't exist anywhere else in the app --
    it isn't assembled from an existing verified source. Authored via the
    same AI-draft-then-Director-review pattern as Quotation.cover_note
    (Amendment 13): ai_content never writes here directly, a draft is
    only ever a transient response the Director reviews and explicitly
    saves through the write endpoint below, same as a drafted cover note
    never auto-sends.

    One row per (sport_id, phase) -- same "Director-set default content"
    shape as PackageContent, not an open list a user adds/removes rows
    from. A sport with no rows yet simply has no Construction Sequence
    section in the Build Guide (Section 16 Part 1's own no-fabrication
    guardrail: never show a placeholder implying content exists when it
    doesn't)."""

    __tablename__ = "construction_sequence_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False)
    phase: Mapped[ConstructionPhase] = mapped_column(Enum(ConstructionPhase, name="construction_phase"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (UniqueConstraint("sport_id", "phase", name="uq_construction_sequence_step_sport_phase"),)
