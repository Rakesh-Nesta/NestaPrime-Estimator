import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FlooringGuide(Base):
    """Parts F.1 (indoor) + F.2 (outdoor): the per-sport flooring guide --
    primary spec, an optional secondary spec, an optional budget spec, and
    the rationale for why. Before this table, the guide lived as a
    hardcoded `_FLOORING_TABLE` dict in sports.py -- functional (it already
    drove B.1's package-tiered recommendation), but a code change was the
    only way to alter it, which the audit's "hardcoded technical
    catalogues" finding (gap #9) named directly. One row per sport, upsert
    like PackageContent (Q.2 rule 6 precedent: Director-only master
    content) -- there's no independent lifecycle to a flooring guide row
    beyond "the current recommendation text for this sport," so no
    is_active: a sport simply has a row or doesn't (no row = no
    recommendation, matching the two sports the original dict already
    left out on purpose -- shooting_range_10m, archery_range)."""

    __tablename__ = "flooring_guides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False)

    primary_spec: Mapped[str] = mapped_column(Text, nullable=False)
    secondary_spec: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_spec: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    # Nullable: a seed-loaded row (the initial migration from the former
    # hardcoded dict) has no real editor yet -- populated the first time a
    # Director actually PUTs new content for this sport.
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (UniqueConstraint("sport_id", name="uq_flooring_guide_sport"),)
