import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.project import SiteCondition, SoilType, UnitSystem


class SiteSurveyStatus(str, enum.Enum):
    """M.7.1: 'Site survey form (blank / filled)' -- a survey starts life
    blank (DRAFT, fields filled in progressively as the Site Engineer
    walks the site) and is marked COMPLETED once the minimum evidence
    (surveyor, date, >=4 photos -- Appendix C: 'photos (min 4)') exists.
    A completed survey is locked, matching this app's other write-once-
    then-verified patterns (CostSheet Draft->Verified, Attachment
    write-once)."""

    DRAFT = "draft"
    COMPLETED = "completed"


class SiteSurvey(Base):
    """Appendix C 'Site survey form (fields)', verbatim: 'Client, site
    address, PIN, contact . sport(s) & count . available area L x W .
    slope / level . soil observed . water-logging . access road width .
    crane access . power (phase, load) . water source . existing
    structures / trees . neighbour constraints . orientation (N-S
    preferred for courts) . photos (min 4) . surveyor & date.' A.3: Site
    Engineer's own duty ('Site survey form, actuals entry'), sent to the
    PM once filled (M.7.1). Every field below maps to exactly one bullet
    in that list; slope/level and soil observed reuse Project's own
    SiteCondition/SoilType enums where the concept is identical, and every
    other field is new since Appendix C asks for more precision (an
    actual road width, a phase and a load, a water *source*) than
    Project's own coarser Screen-1 assumptions (B.1) capture. Values are
    stored on the survey itself, not derived from Project at read time,
    so a later Project edit never silently rewrites what was physically
    observed on the day of the visit -- the same snapshot principle J.1
    applies to a frozen Estimate's rates."""

    __tablename__ = "site_surveys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    status: Mapped[SiteSurveyStatus] = mapped_column(
        Enum(SiteSurveyStatus, name="site_survey_status"), default=SiteSurveyStatus.DRAFT, nullable=False
    )

    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    site_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    sports_and_count: Mapped[str | None] = mapped_column(String(300), nullable=True)
    available_area_length: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    available_area_width: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    area_unit: Mapped[UnitSystem | None] = mapped_column(Enum(UnitSystem, name="unit_system"), nullable=True)

    slope_or_level: Mapped[SiteCondition | None] = mapped_column(Enum(SiteCondition, name="site_condition"), nullable=True)
    soil_observed: Mapped[SoilType | None] = mapped_column(Enum(SoilType, name="soil_type"), nullable=True)
    water_logging_observed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    access_road_width_m: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    crane_access: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    power_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    power_load_kw: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    water_source: Mapped[str | None] = mapped_column(String(200), nullable=True)

    existing_structures_trees: Mapped[str | None] = mapped_column(String(500), nullable=True)
    neighbour_constraints: Mapped[str | None] = mapped_column(String(500), nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    surveyed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    surveyed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
