import math
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.settings import get_current_setting_value
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.flooring_guide import FlooringGuide
from app.models.lighting_standard import LightingLuxStandard, SportPoleCount
from app.models.project import BuildingStatus, Package, Project, SiteCondition, SoilType
from app.models.regional_multiplier import RegionalMultiplier
from app.models.sport import ProjectSport, Sport, SportCategory

sports_router = APIRouter(prefix="/sports", tags=["sports"])
project_sports_router = APIRouter(prefix="/projects", tags=["project-sports"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("sales", "pm", "director")
# A.3: "Site Engineer: Site survey form, actuals entry" -- recording the
# as-built figure is that duty, not the Sales/PM/Director planning
# decision of which sports the project even includes (WRITE_ROLES above).
ACTUALS_WRITE_ROLES = ("site_engineer", "pm", "director")
# Q.2 rule 6: "Master Settings screen is Director-only (PM read-only)."
# The Sport master list (Part C) follows the same convention.
MASTER_WRITE_ROLES = ("director",)

# D.2 Base selection matrix — sport groups as given in the table (not every
# one of the 30 sports is covered; uncovered combinations return None rather
# than guessing a composition the blueprint never specified).
_INDOOR_SMOOTH = {"badminton", "table_tennis", "squash", "gymnasium"}
_TURF_FIELD = {"box_cricket", "football_11", "football_7", "football_5_futsal"}
_HARD_COURT = {"tennis", "basketball_outdoor", "pickleball"}
_ATHLETIC_TRACK = {"athletic_track_400m", "athletic_track_200_250m"}
_POOL = {"swimming_pool_25m", "swimming_pool_50m"}


class BaseRecommendation(BaseModel):
    recommended: str
    alternative: str | None
    why: str


def _recommend_base(
    sport: Sport, building_status: BuildingStatus, soil_type: SoilType
) -> BaseRecommendation | None:
    key = sport.key

    if key in _INDOOR_SMOOTH and building_status in (
        BuildingStatus.EXISTING_BUILDING,
        BuildingStatus.NEW_PEB_BUILDING,
    ):
        return BaseRecommendation(recommended="PCC 4-6 in", alternative="RCC 6 in", why="Smooth for wooden/PU")

    if key in _TURF_FIELD and building_status in (BuildingStatus.OPEN_AIR, BuildingStatus.COVERED_SHED):
        if soil_type == SoilType.NORMAL:
            return BaseRecommendation(
                recommended='WBM 8-10 in (+ PCC 4 in box)', alternative=None, why="Drainage for turf life"
            )
        if soil_type == SoilType.ROCKY:
            return BaseRecommendation(recommended="RCC 6 in direct", alternative=None, why="Rock breaking costly")
        if soil_type == SoilType.BLACK_COTTON:
            return BaseRecommendation(
                recommended="Sand layer 6 in + WBM 10 in + geotextile",
                alternative="RCC 6 in",
                why="Swelling soil",
            )
        return None

    if key in _HARD_COURT and building_status == BuildingStatus.OPEN_AIR and soil_type == SoilType.NORMAL:
        return BaseRecommendation(
            recommended="WBM 6 in + Asphalt 3 in", alternative="PCC 6 in", why="Bounce consistency"
        )

    if key in _ATHLETIC_TRACK and building_status == BuildingStatus.OPEN_AIR and soil_type == SoilType.NORMAL:
        return BaseRecommendation(
            recommended="WBM 8 in + Asphalt 2 in", alternative="RCC + asphalt", why="Even surface"
        )

    if key == "padel" and building_status in (BuildingStatus.OPEN_AIR, BuildingStatus.COVERED_SHED):
        return BaseRecommendation(
            recommended="RCC 6 in over WBM 6 in + perimeter beam",
            alternative=None,
            why="Glass post anchoring",
        )

    if key in _POOL:
        return BaseRecommendation(recommended="RCC 8-12 in shell", alternative=None, why="Water load")

    if key == "kids_play_area" and building_status == BuildingStatus.OPEN_AIR and soil_type == SoilType.NORMAL:
        return BaseRecommendation(recommended="WBM 6 in", alternative="PCC 4 in", why="Impact base")

    if key == "beach_volleyball" and building_status == BuildingStatus.OPEN_AIR:
        return BaseRecommendation(
            recommended="Drainage layer + geotextile + 16 in sand",
            alternative=None,
            why="Sand drainage",
        )

    return None


class StructureRecommendation(BaseModel):
    structure_type: str
    section: str
    height: str
    why: str


_PEB_STRUCTURE_SPORTS = {"badminton", "basketball_indoor", "table_tennis"}
_POOL_KEYS = {"swimming_pool_25m", "swimming_pool_50m"}
_FENCE_HARD_COURT = {"tennis", "pickleball", "basketball_outdoor"}


def _recommend_structure(
    sport: Sport, building_status: BuildingStatus, package: Package
) -> StructureRecommendation | None:
    """E.4, gated by B.1a's 'Structure types allowed' row: Existing building
    is fit-out only (no new structure), so every sport returns None there
    regardless of E.4's table. Sports E.4 never lists for a given status
    return None too, rather than a fabricated recommendation."""
    if building_status == BuildingStatus.EXISTING_BUILDING:
        return None

    key = sport.key

    if key == "box_cricket":
        if package == Package.BUDGET:
            return StructureRecommendation(
                structure_type="A", section='3 in x 3 in', height="12 ft", why="Cost-effective"
            )
        if package == Package.PREMIUM:
            return StructureRecommendation(
                structure_type="B", section='4 in x 4 in', height="14 ft", why="Full containment"
            )
        return None  # standard package: not distinguished by E.4

    if key == "football_5_futsal":
        return StructureRecommendation(
            structure_type="A", section='4 in x 4 in', height="16 ft", why="Larger span"
        )

    if key == "football_7":
        return StructureRecommendation(
            structure_type="B", section='4 in x 4 in', height="18 ft", why="Ball trajectory"
        )

    if key == "badminton" and building_status == BuildingStatus.COVERED_SHED:
        return StructureRecommendation(
            structure_type="C (tall variant) + D",
            section='4 in x 4 in',
            height="24 ft minimum",
            why="Type C standard 10-14 ft is below the badminton minimum; use tall C or Type E",
        )

    if key in _PEB_STRUCTURE_SPORTS and building_status == BuildingStatus.NEW_PEB_BUILDING:
        return StructureRecommendation(
            structure_type="E", section="PEB engineered", height="24-30 ft", why="Permanent"
        )

    if key in _FENCE_HARD_COURT and building_status == BuildingStatus.OPEN_AIR:
        return StructureRecommendation(
            structure_type="G", section='2.5 in GI round', height="10-12 ft", why="Ball containment"
        )

    if key == "padel":
        return StructureRecommendation(
            structure_type="F", section="100x50 RHS", height="13 ft", why="Glass wall"
        )

    if key in ("kids_play_area", "archery_range") and building_status == BuildingStatus.OPEN_AIR:
        return StructureRecommendation(
            structure_type="D", section='2.5 in / 3 in', height="10-12 ft", why="Safety"
        )

    if key in _POOL_KEYS:
        return StructureRecommendation(
            structure_type="G", section='2.5 in GI round', height="4-6 ft", why="Mandatory safety (pool boundary)"
        )

    return None


_SEISMIC_ZONE_LEVEL = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def _wind_zone_level(wind_zone: str) -> int | None:
    match = re.match(r"(\d+)", wind_zone)
    return int(match.group(1)) if match else None


def _structural_signoff_reasons(
    sport: Sport,
    building_status: BuildingStatus,
    project: Project,
    regional: RegionalMultiplier | None,
) -> list[str]:
    """E.5 'Structural responsibility rule': a licensed structural engineer's
    sign-off is mandatory when any of these apply. height > 16 ft and
    span > 30 ft are deliberately not evaluated here — Phase 1b has no
    chosen (as opposed to minimum) structure height or numeric build span
    to check against; everything else below is exact."""
    reasons = []

    if building_status == BuildingStatus.NEW_PEB_BUILDING:
        reasons.append("PEB structure (Type E)")
    if sport.key in _POOL_KEYS:
        reasons.append("Swimming pool")
    if sport.key == "padel":
        reasons.append("Padel (glass loads)")
    if project.soil_type in (SoilType.BLACK_COTTON, SoilType.FILLED):
        reasons.append(f"{project.soil_type.value.replace('_', ' ').capitalize()} soil")
    if project.site_condition == SiteCondition.WATER_LOGGED:
        reasons.append("Water-logged site")
    if project.tender_mode:
        reasons.append("Government / Tender client")
    if regional is not None:
        if regional.coastal:
            reasons.append("Coastal")
        wind_level = _wind_zone_level(regional.wind_zone)
        if wind_level is not None and wind_level >= 4:
            reasons.append(f"Wind zone {regional.wind_zone}")
        seismic_level = _SEISMIC_ZONE_LEVEL.get(regional.seismic_zone)
        if seismic_level is not None and seismic_level >= 4:
            reasons.append(f"Seismic zone {regional.seismic_zone}")

    return reasons


# E.5 / Q.1: the three priced tiers for the auto-added "Structural
# engineer design & sign-off" scope line -- imported by documents.py's
# create_cost_sheet, which is the actual point the line gets added.
STRUCTURAL_SIGNOFF_TIER_SIMPLE = "simple"
STRUCTURAL_SIGNOFF_TIER_PEB_PADEL_POOL = "peb_padel_pool"
STRUCTURAL_SIGNOFF_TIER_MULTICOURT_GOVERNMENT = "multicourt_government"


def project_structural_signoff_tier(db: Session, project: Project) -> str | None:
    """E.5: '... mandatory and auto-added as a scope line when any of
    these apply ...' aggregated across every sport on the project (a
    Cost Sheet is project-wide, not per-sport) into the one of the
    three [confirm] fee tiers this line is priced from: 'Rs 15,000
    simple net structure . Rs 35,000 PEB / Padel / pool . Rs 50,000+
    multi-court or government.' Returns None when no project_sport (or
    project-level condition) triggers the sign-off requirement at all.
    Ties are broken toward the higher tier -- e.g. a government PEB
    project gets the multi-court/government tier, never the lower
    PEB/Padel/pool one -- so the auto-priced default never
    under-estimates the engineer's fee."""
    project_sports = db.query(ProjectSport).filter(ProjectSport.project_id == project.id).all()
    if not project_sports:
        return None

    regional = _get_regional_multiplier(db, project.city)
    any_required = False
    any_peb_padel_pool = False
    for project_sport in project_sports:
        sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
        if sport is None:
            continue
        if _structural_signoff_reasons(sport, project_sport.building_status, project, regional):
            any_required = True
        if (
            project_sport.building_status == BuildingStatus.NEW_PEB_BUILDING
            or sport.key in _POOL_KEYS
            or sport.key == "padel"
        ):
            any_peb_padel_pool = True

    if not any_required:
        return None
    if project.tender_mode or project.number_of_courts > 1:
        return STRUCTURAL_SIGNOFF_TIER_MULTICOURT_GOVERNMENT
    if any_peb_padel_pool:
        return STRUCTURAL_SIGNOFF_TIER_PEB_PADEL_POOL
    return STRUCTURAL_SIGNOFF_TIER_SIMPLE


class FlooringRecommendation(BaseModel):
    primary: str
    secondary: str | None
    budget: str | None
    why: str
    selected: str
    selected_tier: str  # "primary" | "secondary" | "budget"


# F.1 (indoor) + F.2 (outdoor) flooring guides, keyed by sport, live in the
# Director-editable FlooringGuide table (audit gap #9 -- this used to be a
# hardcoded _FLOORING_TABLE dict here). Two sports have no row --
# shooting_range_10m and archery_range -- and correctly get no
# recommendation rather than a guess, same as before the table existed.


def _recommend_flooring(db: Session, sport: Sport, package: Package) -> FlooringRecommendation | None:
    """F.1/F.2, tiered by B.1's own rule for the package field: 'Pre-selects
    flooring, structure, lighting, scope'."""
    guide = db.query(FlooringGuide).filter(FlooringGuide.sport_id == sport.id).first()
    if guide is None:
        return None
    primary, secondary, budget, why = guide.primary_spec, guide.secondary_spec, guide.budget_spec, guide.rationale

    if package == Package.PREMIUM:
        selected, tier = primary, "primary"
    elif package == Package.BUDGET:
        if budget is not None:
            selected, tier = budget, "budget"
        elif secondary is not None:
            selected, tier = secondary, "secondary"
        else:
            selected, tier = primary, "primary"
    else:  # STANDARD
        if secondary is not None:
            selected, tier = secondary, "secondary"
        else:
            selected, tier = primary, "primary"

    return FlooringRecommendation(
        primary=primary, secondary=secondary, budget=budget, why=why,
        selected=selected, selected_tier=tier,
    )


class LightingRecommendation(BaseModel):
    lux_tier: str  # "practice" | "match" | "tournament" — Phase 1b defaults to "match"
    lux_level: int
    area_sqm: float
    mounting_mode: str  # "structure" | "poles"
    pole_count: int | None
    fixture_spec: str
    fixtures: int
    why: str


_SQFT_PER_SQM = 10.7639

# H's lux table, by sport group, lives in the Director-editable
# LightingLuxStandard table (audit gap #9 -- this used to be a hardcoded
# _LUX_TABLE dict here). The sport->category grouping below stays a
# code-level taxonomy ("which sports behave alike"), not a tunable figure.

_COURT_SPORTS = {
    "badminton", "table_tennis", "squash", "basketball_indoor", "basketball_outdoor",
    "volleyball_indoor", "volleyball_outdoor", "kabaddi", "wrestling_boxing_martial_arts",
    "tennis", "padel", "pickleball", "multipurpose_court",
}
_FOOTBALL_CRICKET_SPORTS = {
    "football_11", "football_7", "football_5_futsal", "box_cricket",
    "cricket_practice_nets", "indoor_cricket_nets",
}

# B.1a's own UF/MF table, which "replaces every indoor/outdoor test in this
# document" — more precise than H's generic indoor/outdoor split.
_UF_MF_BY_STATUS: dict[BuildingStatus, tuple[float, float]] = {
    BuildingStatus.EXISTING_BUILDING: (0.7, 0.8),
    BuildingStatus.NEW_PEB_BUILDING: (0.7, 0.8),
    BuildingStatus.COVERED_SHED: (0.6, 0.7),
    BuildingStatus.OPEN_AIR: (0.6, 0.7),
}

# H's pole table (open-air only) lives in the Director-editable
# SportPoleCount table (audit gap #9 -- this used to be a hardcoded
# _POLE_COUNT dict here).

# Only fixture in the blueprint's worked example — 200 W at 130 lm/W.
# Director-editable Master Settings, same "XXX_DEFAULT constant, override
# via Settings" pattern as every other [confirm] figure in this codebase
# (audit gap #9 -- this used to be hardcoded _FIXTURE_LUMENS/_FIXTURE_SPEC
# constants with no override path at all).
DEFAULT_FIXTURE_LUMENS_DEFAULT = 26000.0
DEFAULT_FIXTURE_SPEC_TEXT_DEFAULT = "200 W / 26,000 lm (Phase 1b default fixture)"


def _sport_lux_category(key: str) -> str | None:
    if key in _COURT_SPORTS:
        return "court"
    if key in _FOOTBALL_CRICKET_SPORTS:
        return "football_cricket"
    if key in _POOL_KEYS:
        return "pool"
    if key == "gymnasium":
        return "gym"
    return None


def _recommend_lighting(
    db: Session,
    sport: Sport,
    building_status: BuildingStatus,
    number_of_courts: int,
    structure: StructureRecommendation | None,
) -> LightingRecommendation | None:
    """Part H: fixtures = ceil((area_sqm * lux) / (lumens_per_fixture * UF *
    MF)). area_sqm follows the blueprint's own worked example (which uses
    the sport's PLAYING dimensions, e.g. box cricket 50x25 ft = 116 sqm),
    not the build dimensions the formula's prose label suggests. Sports
    without a playing-area number (variable/custom footprints) or without
    a row in H's lux table return None rather than a guess."""
    if sport.playing_l_ft is None or sport.playing_w_ft is None:
        return None

    category = _sport_lux_category(sport.key)
    if category is None:
        return None

    lux_standard = db.query(LightingLuxStandard).filter(LightingLuxStandard.category == category).first()
    if lux_standard is None:
        return None
    lux_tier = "match" if lux_standard.lux_match is not None else "practice"
    lux_level = lux_standard.lux_match if lux_tier == "match" else lux_standard.lux_practice
    if lux_level is None:
        return None

    area_sqm = float(sport.playing_l_ft) * float(sport.playing_w_ft) * number_of_courts / _SQFT_PER_SQM
    uf, mf = _UF_MF_BY_STATUS[building_status]

    fixture_lumens = float(
        get_current_setting_value(db, "default_fixture_lumens_lm") or DEFAULT_FIXTURE_LUMENS_DEFAULT
    )
    fixture_spec = (
        get_current_setting_value(db, "default_fixture_spec_text") or DEFAULT_FIXTURE_SPEC_TEXT_DEFAULT
    )
    formula_fixtures = math.ceil((area_sqm * lux_level) / (fixture_lumens * uf * mf))

    # E.5: "Types A/B/C/E -> on columns/trusses, no poles; open air/Type
    # D/Type G -> poles" -- driven by the sport's own recommended structure.
    structure_type = structure.structure_type if structure else None
    uses_poles = structure_type is None or structure_type in ("D", "G")

    pole_count_row = (
        db.query(SportPoleCount).filter(SportPoleCount.sport_id == sport.id).first() if uses_poles else None
    )
    pole_count = pole_count_row.pole_count if pole_count_row else None
    fixtures = max(formula_fixtures, pole_count) if pole_count is not None else formula_fixtures
    if uses_poles and pole_count is not None and fixtures % 2 != 0:
        fixtures += 1  # every pole carries at least one fixture

    return LightingRecommendation(
        lux_tier=lux_tier,
        lux_level=lux_level,
        area_sqm=round(area_sqm, 1),
        mounting_mode="poles" if uses_poles else "structure",
        pole_count=pole_count,
        fixture_spec=fixture_spec,
        fixtures=fixtures,
        why=f"{lux_level} lux ({lux_tier}) over {round(area_sqm, 1)} sqm playing area",
    )


class SportOut(BaseModel):
    id: uuid.UUID
    key: str
    display_order: int
    name: str
    category: SportCategory
    playing_dims: str
    build_dims: str
    playing_l_ft: float | None
    playing_w_ft: float | None
    build_l_ft: float | None
    build_w_ft: float | None
    min_clear_height_ft: float | None
    governing_body: str
    source_citation: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@sports_router.get("", response_model=list[SportOut])
def list_sports(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(Sport)
    if not include_inactive:
        query = query.filter(Sport.is_active.is_(True))
    return query.order_by(Sport.display_order).all()


class SportCreate(BaseModel):
    key: str
    display_order: int
    name: str
    category: SportCategory
    playing_dims: str
    build_dims: str
    playing_l_ft: float | None = None
    playing_w_ft: float | None = None
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    min_clear_height_ft: float | None = None
    governing_body: str
    source_citation: str | None = None


class SportUpdate(BaseModel):
    """key is deliberately not editable: every _recommend_* function above
    (and every take-off module elsewhere in this app) matches on
    sport.key, not sport.id -- renaming it would silently strand every
    D.2/E.4/F.1-F.2/H recommendation and every existing sport-specific
    take-off formula for that sport. Create a new sport instead of
    renaming a key that recommendations depend on."""

    display_order: int | None = None
    name: str | None = None
    category: SportCategory | None = None
    playing_dims: str | None = None
    build_dims: str | None = None
    playing_l_ft: float | None = None
    playing_w_ft: float | None = None
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    min_clear_height_ft: float | None = None
    governing_body: str | None = None
    source_citation: str | None = None
    is_active: bool | None = None


@sports_router.post("", response_model=SportOut, status_code=201)
def create_sport(
    payload: SportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    """Part C Sport master admin. A newly created sport has no entry in
    any of this file's _recommend_* tables (they're keyed by sport.key),
    so it gets no Base/Structure/Flooring/Lighting recommendation --
    exactly the same "uncovered combination returns None" behaviour an
    existing, unlisted sport already gets, not an error."""
    if db.query(Sport).filter(Sport.key == payload.key).first():
        raise HTTPException(status_code=409, detail=f"A sport with key '{payload.key}' already exists")
    sport = Sport(**payload.model_dump())
    db.add(sport)
    db.commit()
    db.refresh(sport)
    return sport


@sports_router.patch("/{sport_id}", response_model=SportOut)
def update_sport(
    sport_id: uuid.UUID,
    payload: SportUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    sport = db.query(Sport).filter(Sport.id == sport_id).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sport, field, value)
    db.commit()
    db.refresh(sport)
    return sport


class ProjectSportCreate(BaseModel):
    sport_id: uuid.UUID
    building_status: BuildingStatus
    number_of_courts: int = 1


class ActualDimensionsUpdate(BaseModel):
    actual_l_ft: float | None = None
    actual_w_ft: float | None = None


class BuildSizeUpdate(BaseModel):
    # Amendment 9: null clears back to the sport-wide standard, same
    # nullable-to-clear pattern ActualDimensionsUpdate already uses.
    custom_build_l_ft: float | None = None
    custom_build_w_ft: float | None = None


class DimensionDeviation(BaseModel):
    axis: str  # "length" | "width"
    standard_ft: float
    actual_ft: float
    deviation_percent: float
    status: str  # "green" | "amber" | "red"


# C.3: "deviation_thresholds{amber 2-10%, red >10% or below minimum}" --
# a global Director-set Master Setting, same pattern as every other Q.1
# threshold in this codebase (no dedicated table).
DIMENSION_DEVIATION_AMBER_SETTING_KEY = "dimension_deviation_amber_percent"
DIMENSION_DEVIATION_RED_SETTING_KEY = "dimension_deviation_red_percent"
DIMENSION_DEVIATION_AMBER_DEFAULT = 2.0
DIMENSION_DEVIATION_RED_DEFAULT = 10.0
_DEVIATION_STATUS_SEVERITY = {"green": 0, "amber": 1, "red": 2}


def _get_setting_float(db: Session, key: str, default: float) -> float:
    value = get_current_setting_value(db, key)
    return float(value) if value is not None else default


def _dimension_deviations(db: Session, sport: Sport, project_sport: ProjectSport) -> list[DimensionDeviation]:
    """C.3/M.6: the client PDF's 'standard vs actual' comparison. Only
    computed once an actual figure has actually been recorded (see the
    actual-dimensions endpoint below) -- a project nobody has measured yet
    has nothing to flag, not a fabricated 0% deviation. Sport stores one
    standard figure per axis, not a min/max range, so "below minimum"
    isn't separately modelled -- an undersized actual is flagged by
    deviation magnitude alone, same as an oversized one."""
    amber = _get_setting_float(db, DIMENSION_DEVIATION_AMBER_SETTING_KEY, DIMENSION_DEVIATION_AMBER_DEFAULT)
    red = _get_setting_float(db, DIMENSION_DEVIATION_RED_SETTING_KEY, DIMENSION_DEVIATION_RED_DEFAULT)
    deviations = []
    for axis, standard, actual in (
        ("length", sport.playing_l_ft, project_sport.actual_l_ft),
        ("width", sport.playing_w_ft, project_sport.actual_w_ft),
    ):
        if standard is None or actual is None:
            continue
        standard, actual = float(standard), float(actual)
        pct = abs(actual - standard) / standard * 100 if standard else 0.0
        status = "red" if pct > red else "amber" if pct >= amber else "green"
        deviations.append(
            DimensionDeviation(axis=axis, standard_ft=standard, actual_ft=actual, deviation_percent=round(pct, 1), status=status)
        )
    return deviations


def _worst_deviation_status(deviations: list[DimensionDeviation]) -> str | None:
    if not deviations:
        return None
    return max(deviations, key=lambda d: _DEVIATION_STATUS_SEVERITY[d.status]).status


class ProjectSportOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    sport_id: uuid.UUID
    building_status: BuildingStatus
    number_of_courts: int
    actual_l_ft: float | None = None
    actual_w_ft: float | None = None
    custom_build_l_ft: float | None = None
    custom_build_w_ft: float | None = None
    clear_height_ok: bool = True  # derived; _to_out() sets the real value
    recommended_base: BaseRecommendation | None = None  # derived, D.1/D.2
    recommended_structure: StructureRecommendation | None = None  # derived, E.4
    structural_signoff_required: bool = False  # derived, E.5
    structural_signoff_reasons: list[str] = []  # derived, E.5
    recommended_flooring: FlooringRecommendation | None = None  # derived, F.1/F.2
    recommended_lighting: LightingRecommendation | None = None  # derived, Part H
    dimension_deviations: list[DimensionDeviation] = []  # derived, C.3/M.6
    dimension_deviation_status: str | None = None  # derived, worst of the above

    model_config = ConfigDict(from_attributes=True)


def _to_out(
    db: Session,
    project_sport: ProjectSport,
    sport: Sport,
    project: Project,
    regional: RegionalMultiplier | None,
) -> ProjectSportOut:
    out = ProjectSportOut.model_validate(project_sport)
    out.clear_height_ok = not _violates_min_clear_height(
        sport, project_sport.building_status, project
    )
    out.recommended_base = _recommend_base(sport, project_sport.building_status, project.soil_type)
    out.recommended_structure = _recommend_structure(
        sport, project_sport.building_status, project.package
    )
    out.structural_signoff_reasons = _structural_signoff_reasons(
        sport, project_sport.building_status, project, regional
    )
    out.structural_signoff_required = len(out.structural_signoff_reasons) > 0
    out.recommended_flooring = _recommend_flooring(db, sport, project.package)
    out.recommended_lighting = _recommend_lighting(
        db, sport, project_sport.building_status, project_sport.number_of_courts, out.recommended_structure
    )
    out.dimension_deviations = _dimension_deviations(db, sport, project_sport)
    out.dimension_deviation_status = _worst_deviation_status(out.dimension_deviations)
    return out


def _get_regional_multiplier(db: Session, city: str) -> RegionalMultiplier | None:
    return db.query(RegionalMultiplier).filter(RegionalMultiplier.city == city).first()


def _violates_min_clear_height(
    sport: Sport, building_status: BuildingStatus, project: Project
) -> bool:
    """B.1a: 'Min structure height: building height >= sport min' for
    Existing building / New PEB / Covered shed (Open air has none, '-').
    Phase 1b only captures an actual height value for Existing building
    (B.1 field #14/#15) — PEB and shed heights are chosen later in Part E
    (Structures), not yet built — so only that case can be enforced here."""
    if sport.min_clear_height_ft is None:
        return False
    if building_status != BuildingStatus.EXISTING_BUILDING:
        return False
    if project.existing_building_clear_height_ft is None:
        return False
    return project.existing_building_clear_height_ft < sport.min_clear_height_ft


@project_sports_router.post(
    "/{project_id}/sports", response_model=ProjectSportOut, status_code=201
)
def add_project_sport(
    project_id: uuid.UUID,
    payload: ProjectSportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sport = db.query(Sport).filter(Sport.id == payload.sport_id).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")

    if _violates_min_clear_height(sport, payload.building_status, project):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{sport.name} needs at least {sport.min_clear_height_ft} ft clear height, "
                f"but this building is only {project.existing_building_clear_height_ft} ft (B.1a)"
            ),
        )

    project_sport = ProjectSport(project_id=project_id, **payload.model_dump())
    db.add(project_sport)
    db.commit()
    db.refresh(project_sport)
    regional = _get_regional_multiplier(db, project.city)
    return _to_out(db, project_sport, sport, project, regional)


@project_sports_router.get("/{project_id}/sports", response_model=list[ProjectSportOut])
def list_project_sports(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = db.query(ProjectSport).filter(ProjectSport.project_id == project_id).all()
    sports_by_id = {s.id: s for s in db.query(Sport).all()}
    regional = _get_regional_multiplier(db, project.city)
    return [_to_out(db, row, sports_by_id[row.sport_id], project, regional) for row in rows]


@project_sports_router.patch(
    "/{project_id}/sports/{selection_id}/actual-dimensions", response_model=ProjectSportOut
)
def update_actual_dimensions(
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    payload: ActualDimensionsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ACTUALS_WRITE_ROLES)),
):
    """A.3: 'Site Engineer: Site survey form, actuals entry.' Records the
    as-built figure the client PDF's 'standard vs actual' table (C.3/M.6)
    compares the sport master's own standard dimension against. Both
    fields are nullable so a mistaken entry can be cleared back to
    "not yet measured" rather than stuck at a wrong number."""
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == selection_id, ProjectSport.project_id == project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Project sport not found")

    project = db.query(Project).filter(Project.id == project_id).first()
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()

    old_value = f"{project_sport.actual_l_ft}x{project_sport.actual_w_ft}"
    project_sport.actual_l_ft = payload.actual_l_ft
    project_sport.actual_w_ft = payload.actual_w_ft
    write_audit_log_entry(
        db, current_user, "project_sport", project_sport.id, "actual_dimensions",
        old_value=old_value, new_value=f"{payload.actual_l_ft}x{payload.actual_w_ft}", request=request,
    )
    db.commit()
    db.refresh(project_sport)
    regional = _get_regional_multiplier(db, project.city)
    return _to_out(db, project_sport, sport, project, regional)


@project_sports_router.patch(
    "/{project_id}/sports/{selection_id}/build-size", response_model=ProjectSportOut
)
def update_build_size(
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    payload: BuildSizeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Amendment 9 (Annexure 2): Sport Selection's Court size step. Sets
    this project-sport's own build size, read by every take-off
    calculator's _resolve_dimensions (site_works.py) ahead of the
    sport-wide standard -- so it applies across every take-off for this
    sport on this project without re-entering it per calculator. Only the
    build (surround/clearance) is adjustable: the validation floor here is
    the sport's own federation playing dimensions, which the spec's own
    wording draws as the one thing Quick setup's blind-quoting principle
    still isn't allowed to shrink."""
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == selection_id, ProjectSport.project_id == project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Project sport not found")

    project = db.query(Project).filter(Project.id == project_id).first()
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()

    if payload.custom_build_l_ft is not None and sport.playing_l_ft is not None:
        if payload.custom_build_l_ft < float(sport.playing_l_ft):
            raise HTTPException(
                status_code=422,
                detail=f"Build length can't be smaller than {sport.name}'s playing length "
                f"({sport.playing_l_ft} ft, {sport.governing_body})",
            )
    if payload.custom_build_w_ft is not None and sport.playing_w_ft is not None:
        if payload.custom_build_w_ft < float(sport.playing_w_ft):
            raise HTTPException(
                status_code=422,
                detail=f"Build width can't be smaller than {sport.name}'s playing width "
                f"({sport.playing_w_ft} ft, {sport.governing_body})",
            )

    old_value = f"{project_sport.custom_build_l_ft}x{project_sport.custom_build_w_ft}"
    project_sport.custom_build_l_ft = payload.custom_build_l_ft
    project_sport.custom_build_w_ft = payload.custom_build_w_ft
    write_audit_log_entry(
        db, current_user, "project_sport", project_sport.id, "custom_build_size",
        old_value=old_value, new_value=f"{payload.custom_build_l_ft}x{payload.custom_build_w_ft}", request=request,
    )
    db.commit()
    db.refresh(project_sport)
    regional = _get_regional_multiplier(db, project.city)
    return _to_out(db, project_sport, sport, project, regional)


@project_sports_router.delete("/{project_id}/sports/{selection_id}", status_code=204)
def remove_project_sport(
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    row = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == selection_id, ProjectSport.project_id == project_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Sport selection not found")
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Director-editable catalogues backing _recommend_flooring/_recommend_lighting
# (audit gap #9: these used to be hardcoded dicts in this file). Both follow
# PackageContent's upsert-by-natural-key shape (Q.2 rule 6 precedent:
# Director-only master content) -- there's no independent row lifecycle
# beyond "the current figures for this key," so no is_active/DELETE.
# ---------------------------------------------------------------------------

flooring_guides_router = APIRouter(prefix="/flooring-guides", tags=["flooring-guides"])
lighting_standards_router = APIRouter(prefix="/lighting-standards", tags=["lighting-standards"])


class FlooringGuideOut(BaseModel):
    id: uuid.UUID
    sport_id: uuid.UUID
    primary_spec: str
    secondary_spec: str | None
    budget_spec: str | None
    rationale: str
    updated_by_id: uuid.UUID | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlooringGuideUpsert(BaseModel):
    primary_spec: str = Field(min_length=1)
    secondary_spec: str | None = None
    budget_spec: str | None = None
    rationale: str = Field(min_length=1)


@flooring_guides_router.get("", response_model=list[FlooringGuideOut])
def list_flooring_guides(
    sport_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(FlooringGuide)
    if sport_id is not None:
        query = query.filter(FlooringGuide.sport_id == sport_id)
    return query.order_by(FlooringGuide.sport_id).all()


@flooring_guides_router.put("/{sport_id}", response_model=FlooringGuideOut)
def upsert_flooring_guide(
    sport_id: uuid.UUID,
    payload: FlooringGuideUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    """F.1/F.2: creates the guide row for this sport the first time,
    replaces its content on every later call -- same upsert shape as
    PUT /package-contents/{sport_id}/{tier}."""
    if not db.query(Sport).filter(Sport.id == sport_id).first():
        raise HTTPException(status_code=404, detail="Sport not found")

    guide = db.query(FlooringGuide).filter(FlooringGuide.sport_id == sport_id).first()
    if guide is None:
        guide = FlooringGuide(sport_id=sport_id, updated_by_id=current_user.id)
        db.add(guide)

    guide.primary_spec = payload.primary_spec
    guide.secondary_spec = payload.secondary_spec
    guide.budget_spec = payload.budget_spec
    guide.rationale = payload.rationale
    guide.updated_by_id = current_user.id

    db.commit()
    db.refresh(guide)
    return guide


class LightingLuxStandardOut(BaseModel):
    id: uuid.UUID
    category: str
    lux_practice: int | None
    lux_match: int | None
    lux_tournament: int | None

    model_config = ConfigDict(from_attributes=True)


class LightingLuxStandardUpsert(BaseModel):
    lux_practice: int | None = Field(default=None, ge=0)
    lux_match: int | None = Field(default=None, ge=0)
    lux_tournament: int | None = Field(default=None, ge=0)


@lighting_standards_router.get("/lux", response_model=list[LightingLuxStandardOut])
def list_lighting_lux_standards(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return db.query(LightingLuxStandard).order_by(LightingLuxStandard.category).all()


@lighting_standards_router.put("/lux/{category}", response_model=LightingLuxStandardOut)
def upsert_lighting_lux_standard(
    category: str,
    payload: LightingLuxStandardUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    """Part H's lux table. category is the same "court" / "football_cricket"
    / "pool" / "gym" grouping _sport_lux_category() derives in code -- not
    itself Director-editable (it's a sport taxonomy, not a figure), so this
    endpoint only edits the lux numbers for an existing grouping, not the
    grouping's own membership."""
    standard = db.query(LightingLuxStandard).filter(LightingLuxStandard.category == category).first()
    if standard is None:
        standard = LightingLuxStandard(category=category)
        db.add(standard)

    standard.lux_practice = payload.lux_practice
    standard.lux_match = payload.lux_match
    standard.lux_tournament = payload.lux_tournament

    db.commit()
    db.refresh(standard)
    return standard


class SportPoleCountOut(BaseModel):
    id: uuid.UUID
    sport_id: uuid.UUID
    pole_count: int

    model_config = ConfigDict(from_attributes=True)


class SportPoleCountUpsert(BaseModel):
    pole_count: int = Field(gt=0)


@lighting_standards_router.get("/pole-counts", response_model=list[SportPoleCountOut])
def list_sport_pole_counts(
    sport_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(SportPoleCount)
    if sport_id is not None:
        query = query.filter(SportPoleCount.sport_id == sport_id)
    return query.order_by(SportPoleCount.sport_id).all()


@lighting_standards_router.put("/pole-counts/{sport_id}", response_model=SportPoleCountOut)
def upsert_sport_pole_count(
    sport_id: uuid.UUID,
    payload: SportPoleCountUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    if not db.query(Sport).filter(Sport.id == sport_id).first():
        raise HTTPException(status_code=404, detail="Sport not found")

    row = db.query(SportPoleCount).filter(SportPoleCount.sport_id == sport_id).first()
    if row is None:
        row = SportPoleCount(sport_id=sport_id, pole_count=payload.pole_count)
        db.add(row)
    else:
        row.pole_count = payload.pole_count

    db.commit()
    db.refresh(row)
    return row


@lighting_standards_router.delete("/pole-counts/{sport_id}", status_code=204)
def remove_sport_pole_count(
    sport_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    """Unlike FlooringGuide/LightingLuxStandard (every sport/category
    should always have some current figures), a sport genuinely having NO
    pole-count floor is a meaningful, real state -- most sports never had
    a row in the original _POLE_COUNT dict at all -- so this is the one
    catalogue in this trio with a real delete path."""
    row = db.query(SportPoleCount).filter(SportPoleCount.sport_id == sport_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="No pole-count row for this sport")
    db.delete(row)
    db.commit()
