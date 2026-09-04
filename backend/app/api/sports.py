import math
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import BuildingStatus, Package, Project, SiteCondition, SoilType
from app.models.regional_multiplier import RegionalMultiplier
from app.models.sport import ProjectSport, Sport, SportCategory

sports_router = APIRouter(prefix="/sports", tags=["sports"])
project_sports_router = APIRouter(prefix="/projects", tags=["project-sports"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("sales", "pm", "director")

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


class FlooringRecommendation(BaseModel):
    primary: str
    secondary: str | None
    budget: str | None
    why: str
    selected: str
    selected_tier: str  # "primary" | "secondary" | "budget"


# F.1 (indoor) + F.2 (outdoor) flooring guides, keyed by sport. Two sports
# have no row in either table — shooting_range_10m and archery_range — and
# correctly get no recommendation rather than a guess. tennis (F.2 splits
# hard/clay/grass; our Sport list has one combined "tennis" entry) defaults
# to the hard-court row, the most common surface.
_FLOORING_TABLE: dict[str, tuple[str, str | None, str | None, str]] = {
    "badminton": (
        "Wooden sprung 22 mm + BWF-approved PVC mat 4.5-7 mm", "PU 6 mm", "PVC mat 4.5 mm on PCC",
        "BWF tournaments are played on approved PVC mats laid over a wooden or synthetic base; bare wood is a club finish",
    ),
    "table_tennis": (
        "Hardwood 22 mm or ITTF-approved PVC/PU 4.5-6 mm", "PU 6 mm", "Vinyl 4 mm",
        "ITTF approves wood and synthetic; non-reflective, non-slip",
    ),
    "squash": (
        "Hardwood strip 22 mm (maple/beech) on sprung battens", None, None,
        "WSF specifies unsealed hardwood floor",
    ),
    "basketball_indoor": ("Maple 22 mm", "PU 6 mm", "Vinyl 4 mm", "Tournament standard"),
    "volleyball_indoor": ("PU 6 mm", "Teak 22 mm", "Vinyl 4 mm", "Shock absorption"),
    "gymnasium": (
        "Rubber 8 mm (cardio) / 15-20 mm (free weights)", "Wooden", "Vinyl", "Equipment drops",
    ),
    "kabaddi": ("PU 6 mm / mat", "Wooden", "Vinyl", "Barefoot grip"),
    "wrestling_boxing_martial_arts": ("Rubber 15-20 mm + mat", "PU mat", None, "Falls"),
    "indoor_cricket_nets": ("Turf 30 mm", "Rubber mat", None, "Ball behaviour"),
    "football_11": (
        "FIFA Quality Pro 50-60 mm", "FIFA Quality 50 mm", "Multi-sport 40 mm", "Certification",
    ),
    "football_7": ("Multi-sport 40 mm", "Cricket 40 mm", "Poly 30 mm", "Cost/performance"),
    "football_5_futsal": ("Multi-sport 40 mm", "Cricket 40 mm", "Poly 30 mm", "Cost/performance"),
    "box_cricket": ("Cricket turf 40 mm", "Multi-sport 40 mm", "Poly 35 mm", "Bounce"),
    "cricket_practice_nets": ("Cricket 30 mm", "Multi 30 mm", "Poly 25 mm", "Bowling"),
    "tennis": ("Acrylic 3-5 mm (5-8 coats)", "Synthetic 5 mm", "Concrete + paint", "ITF"),
    "padel": ("Monofilament 12 mm + sand", None, None, "FIP"),
    "pickleball": ("Acrylic 3 mm", "Concrete + coating", None, "USA Pickleball"),
    "basketball_outdoor": ("Acrylic 3 mm", "PU 5 mm", "Concrete + coating", "Weather"),
    "volleyball_outdoor": ("PU 5 mm", "Sand", "Concrete", "All-weather"),
    "beach_volleyball": ("Washed silica sand 16 in", None, None, "FIVB"),
    "hockey_turf": (
        "FIH water-based 12-15 mm (needs irrigation)", "FIH sand-dressed 20-25 mm",
        "Multi-sport 40 mm (non-FIH, school use)",
        "FIH pitches are short-pile; 50 mm turf is football turf and is not hockey-legal",
    ),
    "athletic_track_400m": (
        "Sandwich system 13 mm", "Full-PU 13 mm", "Spray-coat 13 mm (non-certified)",
        "World Athletics certified systems; spike-resistant",
    ),
    "athletic_track_200_250m": (
        "Sandwich system 13 mm", "Full-PU 13 mm", "Spray-coat 13 mm (non-certified)",
        "World Athletics certified systems; spike-resistant",
    ),
    "skating_rink": ("Concrete + coating", "Tiles", None, "Smooth"),
    "kids_play_area": (
        "EPDM system 40 mm (10 mm EPDM wearing + 30 mm SBR base; CFH 1.5 m)",
        "Rubber tiles 25-40 mm", "Grass / sand",
        "Fall protection - 15 mm EPDM alone gives CFH under 1 m",
    ),
    "swimming_pool_25m": ("Anti-slip tiles", "Mosaic", "Marble", "Non-slip"),
    "swimming_pool_50m": ("Anti-slip tiles", "Mosaic", "Marble", "Non-slip"),
    "multipurpose_court": ("Acrylic 3 mm", "PU 5 mm", "Concrete", "Multi-line"),
}


def _recommend_flooring(sport: Sport, package: Package) -> FlooringRecommendation | None:
    """F.1/F.2, tiered by B.1's own rule for the package field: 'Pre-selects
    flooring, structure, lighting, scope'."""
    row = _FLOORING_TABLE.get(sport.key)
    if row is None:
        return None
    primary, secondary, budget, why = row

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

# H's lux table, by sport group. None = that tier has no figure in the
# table (e.g. Gym has only a practice figure).
_LUX_TABLE: dict[str, dict[str, int | None]] = {
    "court": {"practice": 200, "match": 500, "tournament": 750},
    "football_cricket": {"practice": 200, "match": 500, "tournament": 750},  # tournament up to 1000 per H
    "pool": {"practice": 300, "match": 500, "tournament": None},
    "gym": {"practice": 300, "match": None, "tournament": None},
}

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

# H's pole table (open-air only): lower bound of each range used as the
# Phase 1b default fixture-count floor.
_POLE_COUNT: dict[str, int] = {
    "box_cricket": 4,
    "football_7": 6,
    "tennis": 4,
    "basketball_outdoor": 4,
    "padel": 4,
    "swimming_pool_25m": 6,
    "swimming_pool_50m": 6,
}

# Only fixture in the blueprint's worked example — 200 W at 130 lm/W.
_FIXTURE_LUMENS = 26000
_FIXTURE_SPEC = "200 W / 26,000 lm (Phase 1b default fixture)"


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

    lux_by_tier = _LUX_TABLE[category]
    lux_tier = "match" if lux_by_tier["match"] is not None else "practice"
    lux_level = lux_by_tier[lux_tier]
    if lux_level is None:
        return None

    area_sqm = float(sport.playing_l_ft) * float(sport.playing_w_ft) * number_of_courts / _SQFT_PER_SQM
    uf, mf = _UF_MF_BY_STATUS[building_status]

    formula_fixtures = math.ceil((area_sqm * lux_level) / (_FIXTURE_LUMENS * uf * mf))

    # E.5: "Types A/B/C/E -> on columns/trusses, no poles; open air/Type
    # D/Type G -> poles" -- driven by the sport's own recommended structure.
    structure_type = structure.structure_type if structure else None
    uses_poles = structure_type is None or structure_type in ("D", "G")

    pole_count = _POLE_COUNT.get(sport.key) if uses_poles else None
    fixtures = max(formula_fixtures, pole_count) if pole_count is not None else formula_fixtures
    if uses_poles and pole_count is not None and fixtures % 2 != 0:
        fixtures += 1  # every pole carries at least one fixture

    return LightingRecommendation(
        lux_tier=lux_tier,
        lux_level=lux_level,
        area_sqm=round(area_sqm, 1),
        mounting_mode="poles" if uses_poles else "structure",
        pole_count=pole_count,
        fixture_spec=_FIXTURE_SPEC,
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

    model_config = ConfigDict(from_attributes=True)


@sports_router.get("", response_model=list[SportOut])
def list_sports(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return db.query(Sport).order_by(Sport.display_order).all()


class ProjectSportCreate(BaseModel):
    sport_id: uuid.UUID
    building_status: BuildingStatus
    number_of_courts: int = 1


class ProjectSportOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    sport_id: uuid.UUID
    building_status: BuildingStatus
    number_of_courts: int
    clear_height_ok: bool = True  # derived; _to_out() sets the real value
    recommended_base: BaseRecommendation | None = None  # derived, D.1/D.2
    recommended_structure: StructureRecommendation | None = None  # derived, E.4
    structural_signoff_required: bool = False  # derived, E.5
    structural_signoff_reasons: list[str] = []  # derived, E.5
    recommended_flooring: FlooringRecommendation | None = None  # derived, F.1/F.2
    recommended_lighting: LightingRecommendation | None = None  # derived, Part H

    model_config = ConfigDict(from_attributes=True)


def _to_out(
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
    out.recommended_flooring = _recommend_flooring(sport, project.package)
    out.recommended_lighting = _recommend_lighting(
        sport, project_sport.building_status, project_sport.number_of_courts, out.recommended_structure
    )
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
    return _to_out(project_sport, sport, project, regional)


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
    return [_to_out(row, sports_by_id[row.sport_id], project, regional) for row in rows]


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
