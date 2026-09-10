import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LightingLuxStandard(Base):
    """Part H's lux table, by sport group ("court", "football_cricket",
    "pool", "gym" -- the same four category keys _recommend_lighting
    already derives from a sport's own key via _sport_lux_category(),
    which stays a code-level taxonomy since it's "which sports behave
    alike," not a tunable figure). practice/match/tournament are
    nullable since not every category has a figure for every tier in H's
    own table (e.g. Gym has only a practice figure). Before this table,
    these lived as a hardcoded `_LUX_TABLE` dict in sports.py -- part of
    the audit's "hardcoded technical catalogues" finding (gap #9,
    grouped there as "FIXTURE_MASTER"), display-only (feeds
    ProjectSportOut.recommended_lighting), never a cost figure."""

    __tablename__ = "lighting_lux_standards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(30), nullable=False)

    lux_practice: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lux_match: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lux_tournament: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("category", name="uq_lighting_lux_standard_category"),)


class SportPoleCount(Base):
    """Part H's pole table (open-air only): the lower bound of each
    range, used as the Phase 1b default fixture-count floor once
    _recommend_lighting decides a sport mounts on poles rather than
    structure (E.5: Type D/G or no recommended structure at all). Only
    the specific outdoor, pole-mounted sports named in H's own table
    have a row -- every other sport has none, meaning "no pole-count
    floor applies" (mounting mode is still derived live from the sport's
    structure recommendation, not from row presence here). Same
    hardcoded-dict-to-table gap as LightingLuxStandard (`_POLE_COUNT` in
    sports.py, audit gap #9)."""

    __tablename__ = "sport_pole_counts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False)
    pole_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("sport_id", name="uq_sport_pole_count_sport"),)
