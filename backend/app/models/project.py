import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectType(str, enum.Enum):  # B.1 field #1
    """B.1's own auto-effect text: 'Resurfacing hides Site Prep, Base,
    Structure; shows Flooring + Line Marking + Accessories. Supply only
    = goods delivered without installation: no labour, no site prep.'
    Repair has no auto-effect text of its own anywhere in the blueprint
    -- it's named only as an enum option and grouped with Resurfacing
    for M.2 rule 8's small-job fast-track threshold, so no scope-hiding
    is implemented for it here (there's nothing to implement). K.1b/K.4
    (the latest, authoritative pricing text) confirm GST and the pricing
    engine itself are NOT project-type-dependent -- flat 18% GST applies
    universally, and Supply Only is priced identically to New Build
    ("same model as turnkey, not a separate goods-pricing format") --
    so no separate pricing path exists for any project type."""

    NEW_BUILD = "new_build"
    RESURFACING = "resurfacing"
    REPAIR = "repair"
    SUPPLY_ONLY = "supply_only"


class SiteCondition(str, enum.Enum):  # B.1 field #4
    LEVEL = "level"
    SLOPED = "sloped"
    WATER_LOGGED = "water_logged"


class SoilType(str, enum.Enum):  # B.1 field #5
    NORMAL = "normal"
    ROCKY = "rocky"
    BLACK_COTTON = "black_cotton"
    SANDY = "sandy"
    FILLED = "filled"  # loose


class BuildingStatus(str, enum.Enum):  # B.1 field #6 / B.1a
    EXISTING_BUILDING = "existing_building"
    NEW_PEB_BUILDING = "new_peb_building"
    OPEN_AIR = "open_air"
    COVERED_SHED = "covered_shed"


class SiteAccess(str, enum.Enum):  # B.1 field #7
    GOOD = "good"
    NARROW_ROAD = "narrow_road"  # < 4 m
    NO_CRANE_ACCESS = "no_crane_access"


class PowerAvailable(str, enum.Enum):  # B.1 field #8
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"


class UnitSystem(str, enum.Enum):  # B.1 field #11
    FEET = "feet"
    METRES = "metres"


class Package(str, enum.Enum):  # B.1 field #12
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"


class Project(Base):
    """Part O PROJECTS + Part B.1's setup fields (Screen 1, before sport
    selection). Field numbers in comments match B.1's own numbering."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )

    # #1 Project type -- see ProjectType's own docstring for what its
    # auto-effects actually are (and aren't).
    project_type: Mapped[ProjectType] = mapped_column(
        Enum(ProjectType, name="project_type"), default=ProjectType.NEW_BUILD, nullable=False
    )

    # #2 City/district — free text so "Other" is always representable; known
    # cities should match a RegionalMultiplier.city row, but nothing enforces
    # that at the DB level, matching B.1's own "Other" allowance.
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    site_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    site_state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # #4 Distance from nearest NestaPrime hub (km). hub_id records WHICH
    # hub (Part O HUBS) the PM measured from; distance_km is still the
    # manual km entry itself (M.4a item 5) — PIN-code lookup is a Phase 7
    # integration. hub_id is nullable so existing/older projects and any
    # site with no NestaPrime hub nearby remain representable.
    hub_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hubs.id"), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)

    site_condition: Mapped[SiteCondition] = mapped_column(
        Enum(SiteCondition, name="site_condition"), nullable=False
    )
    soil_type: Mapped[SoilType] = mapped_column(Enum(SoilType, name="soil_type"), nullable=False)

    # #6 Project-default building status. Asked again per sport in Module 1
    # (a multi-sport project can mix statuses); this is just the default.
    building_status: Mapped[BuildingStatus] = mapped_column(
        Enum(BuildingStatus, name="building_status"), nullable=False
    )

    site_access: Mapped[SiteAccess] = mapped_column(
        Enum(SiteAccess, name="site_access"), nullable=False
    )
    power_available: Mapped[PowerAvailable] = mapped_column(
        Enum(PowerAvailable, name="power_available"), nullable=False
    )
    water_available: Mapped[bool] = mapped_column(Boolean, nullable=False)  # #9

    number_of_courts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # #10
    unit_system: Mapped[UnitSystem] = mapped_column(  # #11
        Enum(UnitSystem, name="unit_system"), default=UnitSystem.FEET, nullable=False
    )
    package: Mapped[Package] = mapped_column(Enum(Package, name="package"), nullable=False)  # #12

    # #13 Safe bearing capacity — kN/sqm from soil report. Blank until the
    # report exists; mandatory (enforced at the API, not the DB) for PEB,
    # pool, black-cotton, rocky, filled and water-logged sites (D.4).
    safe_bearing_capacity: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # #14 Only meaningful when building_status = existing_building; checked
    # against the sport's minimum clear height (B.1a) once sports are added.
    existing_building_clear_height_ft: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )

    # B.2: Client = Government auto-switches this on. Not editable directly —
    # derived from the client's type at creation time (see api/projects.py).
    tender_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
