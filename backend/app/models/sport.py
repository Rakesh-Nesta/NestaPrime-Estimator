import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.project import BuildingStatus


class SportCategory(str, enum.Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class Sport(Base):
    """Part C — MASTER SPORT LIST (Module 1), 30 sports from C.1/C.2.

    Seeded once (see app/seed_data.py); Director-only CRUD now exists at
    POST/PATCH /sports (sports.py), closing the Phase 1b "no admin UI"
    gap. is_active governs the Sport Selection screen's default listing
    -- deactivating retires a sport without breaking existing
    ProjectSport rows that reference it."""

    __tablename__ = "sports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)  # C.1/C.2 "#" column
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[SportCategory] = mapped_column(
        Enum(SportCategory, name="sport_category"), nullable=False
    )
    playing_dims: Mapped[str] = mapped_column(String(200), nullable=False)
    build_dims: Mapped[str] = mapped_column(String(300), nullable=False)

    # Numeric L x W (ft) parsed from the C.1/C.2 text above, club/base
    # figure where the table gives a club/tournament pair. Null where the
    # dimension is genuinely variable (per-lane, custom footprint, oval
    # track) rather than a fixed rectangle — used by Part H's lighting
    # fixture-count formula (playing area) and reserved for Part D.3/E.2's
    # take-off math once those are built.
    playing_l_ft: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    playing_w_ft: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    build_l_ft: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    build_w_ft: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)

    # Indoor sports only (C.1) — checked against the project/sport's
    # building clear height per B.1a: "Min structure height: building
    # height >= sport min". Null for outdoor sports (C.2, no ceiling).
    min_clear_height_ft: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)

    governing_body: Mapped[str] = mapped_column(String(150), nullable=False)
    # Printed on the client PDF later (C.3: source_citation), e.g.
    # "BWF Statutes Sec 1.1, 2024".
    source_citation: Mapped[str | None] = mapped_column(String(200), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProjectSport(Base):
    """A sport selected for a project (Module 1 output). Building status is
    asked again per sport (B.1 field #7 note / B.1a) — a multi-sport project
    can mix an indoor court inside an existing building with an outdoor
    field, so it is not simply inherited from the project's default."""

    __tablename__ = "project_sports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sports.id"), nullable=False
    )
    building_status: Mapped[BuildingStatus] = mapped_column(
        Enum(BuildingStatus, name="building_status"), nullable=False
    )
    number_of_courts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
