import math
import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, CostSheetStatus, WorkPackage
from app.models.netting_grade import NettingGrade
from app.models.rate_item import LabourCategory, RateSource
from app.models.sport import ProjectSport, Sport

structures_router = APIRouter(tags=["structures"])
netting_grades_router = APIRouter(prefix="/netting-grades", tags=["netting-grades"])

COST_ROLES = ("pm", "director")
# The catalogue's rate_per_sqm is real cost-side pricing, same footing as
# RateItem (rate_items.py) -- Sales never sees it (K.3).
NETTING_CATALOG_READ_ROLES = ("pm", "director", "procurement", "site_engineer")
# Q.2 rule 6 precedent: "Master Settings screen is Director-only."
NETTING_CATALOG_WRITE_ROLES = ("director",)

FT_TO_M = 0.3048
SQFT_TO_SQM = 0.09290304
CUFT_TO_CUM = 0.0283168

# E.2 / J.3: wastage is applied to the ORDERED QUANTITY (matching J.3's
# "Order qty" = theoretical qty x (1 + wastage%) convention for every other
# material in the consumption sheet), not to the cost -- mathematically
# equivalent to E.2's "x (1 + wastage 5%)" phrasing on cost, since it's the
# same multiplication either way.
STEEL_WASTAGE_PERCENT = 5.0
# E.2: "consumables (electrodes 2% of steel cost)" -- folded straight into
# the effective steel rate rather than emitted as its own tiny line, so it
# doesn't pick up an unrelated labour-category markup of its own.
CONSUMABLES_PERCENT_OF_STEEL = 2.0
NETTING_WASTAGE_PERCENT = 10.0  # J.3: "netting sqm + 10%"
COASTAL_STEEL_UPLIFT_PERCENT = 15.0  # E.5: "Coastal -> ... +15% MS"


class StructureType(str, Enum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"


TAKEOFF_SUPPORTED_TYPES = {StructureType.A, StructureType.B, StructureType.C, StructureType.D, StructureType.G}


class Section(str, Enum):
    SHS_2_5 = "shs_2_5"
    SHS_3 = "shs_3"
    SHS_4 = "shs_4"
    SHS_5 = "shs_5"
    SHS_6 = "shs_6"
    RHS_80_40 = "rhs_80_40"
    RHS_100_50 = "rhs_100_50"
    ROUND_2 = "round_2"
    ROUND_2_5 = "round_2_5"
    ROUND_3 = "round_3"


ROUND_SECTIONS = {Section.ROUND_2, Section.ROUND_2_5, Section.ROUND_3}

# E.2 pipe weight table (kg/m), keyed by section then wall thickness (mm).
# Round sections carry one IS 1239 medium-class weight -- no thickness choice.
PIPE_WEIGHT_KG_PER_M: dict[Section, dict[float | None, float]] = {
    Section.SHS_2_5: {2.0: 3.8, 2.5: 4.7, 3.0: 5.6, 4.0: 7.3},
    Section.SHS_3: {2.0: 4.6, 2.5: 5.7, 3.0: 6.8, 4.0: 8.9},
    Section.SHS_4: {2.0: 6.1, 2.5: 7.6, 3.0: 9.1, 4.0: 12.0},
    Section.SHS_5: {2.0: 7.7, 2.5: 9.6, 3.0: 11.5, 4.0: 15.1},
    Section.SHS_6: {2.0: 9.3, 2.5: 11.6, 3.0: 13.8, 4.0: 18.2},
    Section.RHS_80_40: {2.0: 3.6, 2.5: 4.5, 3.0: 5.3, 4.0: 6.9},
    Section.RHS_100_50: {2.0: 4.6, 2.5: 5.7, 3.0: 6.8, 4.0: 8.9},
    Section.ROUND_2: {None: 3.6},
    Section.ROUND_2_5: {None: 5.1},
    Section.ROUND_3: {None: 6.4},
}

# E.2's wind-zone upsize note ("steps to the next row for section") only
# makes sense for the square-section family it's a table of rows within;
# RHS/round sections have no defined "next" so they upsize thickness only.
SHS_UPSIZE_ORDER = [Section.SHS_2_5, Section.SHS_3, Section.SHS_4, Section.SHS_5, Section.SHS_6]
THICKNESS_UPSIZE_ORDER = [2.0, 2.5, 3.0, 4.0]

# E.1's own proven-design defaults per type: column spacing S (ft), footing
# size (ft, square footing), foundation depth D (ft). These are engineering
# standards ("NestaPrime's proven designs for normal conditions", E.5), not
# Master-Settings-editable rates -- overridable per call, not per Q.1.
STRUCTURE_DEFAULTS = {
    StructureType.A: {"spacing_ft": 10.0, "footing_ft": 1.5, "depth_ft": 3.0},
    StructureType.B: {"spacing_ft": 9.0, "footing_ft": 2.0, "depth_ft": 4.0},
    StructureType.C: {"spacing_ft": 11.0, "footing_ft": 1.5, "depth_ft": 2.5},
    StructureType.D: {"spacing_ft": 10.0, "footing_ft": 1.0, "depth_ft": 2.0},
    StructureType.G: {"spacing_ft": 10.0, "footing_ft": 0.75, "depth_ft": 2.0},
}


def _ceil_div(value: float, divisor: float) -> int:
    return math.ceil(value / divisor)


def _resolve_section_and_thickness(
    section: Section, wall_thickness_mm: float | None, wind_zone: int | None
) -> tuple[Section, float | None]:
    if section in ROUND_SECTIONS:
        wall_thickness_mm = None
    if wind_zone is not None and wind_zone >= 4:
        if section in SHS_UPSIZE_ORDER:
            idx = SHS_UPSIZE_ORDER.index(section)
            section = SHS_UPSIZE_ORDER[min(idx + 1, len(SHS_UPSIZE_ORDER) - 1)]
        if wall_thickness_mm is not None and wall_thickness_mm in THICKNESS_UPSIZE_ORDER:
            idx = THICKNESS_UPSIZE_ORDER.index(wall_thickness_mm)
            wall_thickness_mm = THICKNESS_UPSIZE_ORDER[min(idx + 1, len(THICKNESS_UPSIZE_ORDER) - 1)]
    return section, wall_thickness_mm


def _pipe_weight_kg_per_m(section: Section, wall_thickness_mm: float | None) -> float:
    table = PIPE_WEIGHT_KG_PER_M[section]
    if wall_thickness_mm not in table:
        raise HTTPException(
            status_code=422, detail=f"No E.2 pipe weight for {section.value} at {wall_thickness_mm}mm"
        )
    return table[wall_thickness_mm]


def _geometry(structure_type: StructureType, L: float, W: float, H: float, S: float, tall_variant: bool):
    """E.2a take-off rules (L, W = build dimensions ft; H = height ft;
    S = column spacing ft). Returns (columns, beam_length_ft, trusses,
    truss_span_ft, purlins_m, envelope_area_sqft, envelope_label)."""
    if structure_type == StructureType.A:
        columns = 2 * (_ceil_div(L, S) + 1) + _ceil_div(W, S) - 1
        beam_length_ft = 2 * L + W  # perimeter minus the open end (taken as a W-side)
        trusses = _ceil_div(L, S) + 1
        truss_span_ft = W
        purlins_m = _ceil_div(W * FT_TO_M, 1.2) * (L * FT_TO_M)
        envelope_area_sqft = (2 * L + W) * H + L * W
        envelope_label = "Netting"
    elif structure_type in (StructureType.B, StructureType.C):
        columns = 2 * (_ceil_div(L, S) + 1) + 2 * (_ceil_div(W, S) - 1)
        beam_length_ft = 2 * (L + W)
        trusses = _ceil_div(L, S) + 1
        truss_span_ft = W
        purlins_m = _ceil_div(W * FT_TO_M, 1.2) * (L * FT_TO_M)
        if structure_type == StructureType.B:
            envelope_area_sqft = 2 * (L + W) * H + L * W
            envelope_label = "Netting"
        else:  # C: roof shed only -- no wall netting, roof sheet with 10% allowance
            envelope_area_sqft = L * W * 1.1
            envelope_label = "Roof sheeting"
    elif structure_type == StructureType.D:
        columns = 2 * (_ceil_div(L, S) + 1) + 2 * (_ceil_div(W, S) - 1)
        beam_length_ft = 2 * (L + W)
        trusses = 0
        truss_span_ft = 0.0
        purlins_m = 0.0
        envelope_area_sqft = 2 * (L + W) * H  # walls only, no roof
        envelope_label = "Netting"
    elif structure_type == StructureType.G:
        perimeter = 2 * (L + W)
        columns = _ceil_div(perimeter, S)
        beam_length_ft = 2 * perimeter  # top rail + mid rail
        trusses = 0
        truss_span_ft = 0.0
        purlins_m = 0.0
        envelope_area_sqft = perimeter * H
        envelope_label = "Chain-link"
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Type {structure_type.value.upper()} is priced from a vendor quote (E.2a), not a formula take-off "
                "-- add it as a manual CostSheetLine instead"
            ),
        )
    return columns, beam_length_ft, trusses, truss_span_ft, purlins_m, envelope_area_sqft, envelope_label


class StructureTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    structure_type: StructureType
    section: Section
    wall_thickness_mm: float | None = None
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    height_ft: float = Field(gt=0)
    column_spacing_ft: float | None = Field(default=None, gt=0)
    foundation_depth_ft: float | None = Field(default=None, gt=0)
    tall_variant: bool = False  # Type C only (E.1: "tall variant")
    steel_rate_per_kg: float = Field(gt=0)
    # E.3: either pick a catalogue grade (its current Director-set rate is
    # used) or enter a bare rate directly, same escape hatch as the
    # accessory catalog's own custom_items -- a one-off spec the four
    # standard grades don't cover shouldn't be blocked.
    netting_grade_id: uuid.UUID | None = None
    netting_rate_per_sqm: float | None = Field(default=None, gt=0)
    concrete_rate_per_cum: float = Field(gt=0)
    finish_rate_per_kg: float | None = Field(default=None, ge=0)  # paint, or galvanising if coastal
    wind_zone: int | None = Field(default=None, ge=1, le=5)
    seismic_zone: str | None = None  # "I".."V"
    coastal: bool = False

    @model_validator(mode="after")
    def _netting_rate_or_grade(self):
        if self.netting_grade_id is None and self.netting_rate_per_sqm is None:
            raise ValueError("netting_rate_per_sqm or netting_grade_id is required")
        return self


class StructureTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@structures_router.post(
    "/cost-sheets/{cost_sheet_id}/structures", response_model=StructureTakeoffOut, status_code=201
)
def add_structure_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: StructureTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """Part E: computes a structure's quantity take-off (columns, beams,
    trusses, purlins, envelope area, foundations) and writes it straight
    into the Cost Sheet as real CostSheetLine rows -- the first part of the
    blueprint that generates lines programmatically instead of by hand."""
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status != CostSheetStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Structures can only be added to a Draft cost sheet")
    if payload.structure_type not in TAKEOFF_SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Type {payload.structure_type.value.upper()} is priced from a vendor quote (E.2a), not a formula "
                "take-off -- add it as a manual CostSheetLine instead"
            ),
        )

    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == payload.project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()

    if sport.min_clear_height_ft is not None and payload.height_ft < float(sport.min_clear_height_ft):
        raise HTTPException(
            status_code=400,
            detail=f"{sport.name} needs at least {sport.min_clear_height_ft} ft clear height (E.4)",
        )

    defaults = STRUCTURE_DEFAULTS[payload.structure_type]
    L = payload.build_l_ft if payload.build_l_ft is not None else (float(sport.build_l_ft) if sport.build_l_ft else None)
    W = payload.build_w_ft if payload.build_w_ft is not None else (float(sport.build_w_ft) if sport.build_w_ft else None)
    if L is None or W is None:
        raise HTTPException(
            status_code=422,
            detail="build_l_ft/build_w_ft are required -- this sport has no default build dimensions",
        )
    S = payload.column_spacing_ft or defaults["spacing_ft"]
    footing_ft = 2.0 if (payload.structure_type == StructureType.C and payload.tall_variant) else defaults["footing_ft"]
    depth_ft = payload.foundation_depth_ft or defaults["depth_ft"]
    if payload.seismic_zone in ("IV", "V"):
        depth_ft += 0.5  # E.5: "Seismic IV-V -> Foundation +0.5 ft depth & width"

    section, wall_thickness_mm = _resolve_section_and_thickness(payload.section, payload.wall_thickness_mm, payload.wind_zone)
    kg_per_m = _pipe_weight_kg_per_m(section, wall_thickness_mm)

    columns, beam_length_ft, trusses, truss_span_ft, purlins_m, envelope_area_sqft, envelope_label = _geometry(
        payload.structure_type, L, W, payload.height_ft, S, payload.tall_variant
    )

    netting_grade = None
    if payload.netting_grade_id is not None:
        if envelope_label != "Netting":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"netting_grade_id doesn't apply to Type {payload.structure_type.value.upper()}'s envelope "
                    f"({envelope_label}) -- pass netting_rate_per_sqm directly for that material"
                ),
            )
        netting_grade = db.query(NettingGrade).filter(NettingGrade.id == payload.netting_grade_id).first()
        if not netting_grade:
            raise HTTPException(status_code=404, detail="Netting grade not found")
    netting_rate = (
        payload.netting_rate_per_sqm if payload.netting_rate_per_sqm is not None else float(netting_grade.rate_per_sqm)
    )

    column_length_m = columns * (payload.height_ft + depth_ft) * FT_TO_M
    beam_length_m = beam_length_ft * FT_TO_M
    truss_length_m = trusses * truss_span_ft * FT_TO_M
    steel_length_m = column_length_m + beam_length_m + truss_length_m + purlins_m

    steel_kg_theoretical = steel_length_m * kg_per_m
    steel_kg_ordered = steel_kg_theoretical * (1 + STEEL_WASTAGE_PERCENT / 100)

    envelope_area_sqm = envelope_area_sqft * SQFT_TO_SQM
    envelope_area_ordered_sqm = envelope_area_sqm * (1 + NETTING_WASTAGE_PERCENT / 100)

    foundations_count = columns
    foundation_volume_cum = foundations_count * footing_ft * footing_ft * depth_ft * CUFT_TO_CUM

    steel_rate_effective = payload.steel_rate_per_kg
    if payload.coastal:
        steel_rate_effective *= 1 + COASTAL_STEEL_UPLIFT_PERCENT / 100
    steel_rate_effective *= 1 + CONSUMABLES_PERCENT_OF_STEEL / 100

    ms_fab_category = db.query(LabourCategory).filter(LabourCategory.key == "ms_fabrication_erection").first()
    netting_category = db.query(LabourCategory).filter(LabourCategory.key == "netting").first()
    civil_category = db.query(LabourCategory).filter(LabourCategory.key == "civil_base_site_prep").first()

    type_label = payload.structure_type.value.upper()
    section_label = section.value.replace("_", " ").upper()
    steel_item_name = f"Type {type_label} structure -- {section_label}"
    if wall_thickness_mm is not None:
        steel_item_name += f" {wall_thickness_mm}mm"
    if payload.coastal:
        steel_item_name += " (coastal, hot-dip galvanised)"

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.STRUCTURE,
            category="MS structure",
            item_name=steel_item_name,
            unit="kg",
            quantity=round(steel_kg_ordered, 2),
            rate=round(steel_rate_effective, 2),
            source=RateSource.MANUAL,
            labour_category_id=ms_fab_category.id if ms_fab_category else None,
            wastage_percent=STEEL_WASTAGE_PERCENT,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.STRUCTURE,
            category=envelope_label,
            item_name=(
                f"{envelope_label} -- Type {type_label}" + (f" -- {netting_grade.name}" if netting_grade else "")
            ),
            unit="sqm",
            quantity=round(envelope_area_ordered_sqm, 2),
            rate=round(netting_rate, 2),
            source=RateSource.MANUAL,
            labour_category_id=netting_category.id if netting_category else None,
            wastage_percent=NETTING_WASTAGE_PERCENT,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.CIVIL,
            category="Foundation",
            item_name=f"RCC M25 footing {footing_ft}x{footing_ft}x{depth_ft}ft x{foundations_count}",
            unit="cum",
            quantity=round(foundation_volume_cum, 3),
            rate=payload.concrete_rate_per_cum,
            source=RateSource.MANUAL,
            labour_category_id=civil_category.id if civil_category else None,
        ),
    ]

    if payload.finish_rate_per_kg is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.STRUCTURE,
                category="Finish",
                item_name="Hot-dip galvanising" if payload.coastal else "Primer/paint",
                unit="kg",
                quantity=round(steel_kg_ordered, 2),
                rate=payload.finish_rate_per_kg,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return StructureTakeoffOut(
        breakdown={
            "columns": columns,
            "foundations_count": foundations_count,
            "trusses": trusses,
            "resolved_section": section.value,
            "resolved_wall_thickness_mm": wall_thickness_mm,
            "steel_length_m": round(steel_length_m, 3),
            "steel_kg_theoretical": round(steel_kg_theoretical, 2),
            "steel_kg_ordered": round(steel_kg_ordered, 2),
            "envelope_area_sqm": round(envelope_area_sqm, 2),
            "envelope_area_ordered_sqm": round(envelope_area_ordered_sqm, 2),
            "netting_grade": netting_grade.name if netting_grade else None,
            "netting_rate_per_sqm": round(netting_rate, 2),
            "foundation_volume_cum": round(foundation_volume_cum, 3),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )


# --------------------------------------------------------------------------
# E.3 netting grade catalogue -- Director-editable, replacing the bare
# PM-entered netting_rate_per_sqm that used to be the only option (the
# audit's ranked gap #12).
# --------------------------------------------------------------------------


class NettingGradeOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    material: str
    twine: str | None
    mesh: str
    uv_stabilized: bool | None
    typical_use: str
    rate_per_sqm: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@netting_grades_router.get("", response_model=list[NettingGradeOut])
def list_netting_grades(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*NETTING_CATALOG_READ_ROLES)),
):
    query = db.query(NettingGrade)
    if not include_inactive:
        query = query.filter(NettingGrade.is_active.is_(True))
    return query.order_by(NettingGrade.key).all()


class NettingGradeCreate(BaseModel):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    material: str = Field(min_length=1)
    twine: str | None = None
    mesh: str = Field(min_length=1)
    uv_stabilized: bool | None = None
    typical_use: str = Field(min_length=1)
    rate_per_sqm: float = Field(gt=0)


class NettingGradeUpdate(BaseModel):
    name: str | None = None
    material: str | None = None
    twine: str | None = None
    mesh: str | None = None
    uv_stabilized: bool | None = None
    typical_use: str | None = None
    rate_per_sqm: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


@netting_grades_router.post("", response_model=NettingGradeOut, status_code=201)
def create_netting_grade(
    payload: NettingGradeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*NETTING_CATALOG_WRITE_ROLES)),
):
    if db.query(NettingGrade).filter(NettingGrade.key == payload.key).first():
        raise HTTPException(status_code=409, detail=f"Netting grade '{payload.key}' already exists")
    grade = NettingGrade(**payload.model_dump())
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade


@netting_grades_router.patch("/{grade_id}", response_model=NettingGradeOut)
def update_netting_grade(
    grade_id: uuid.UUID,
    payload: NettingGradeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*NETTING_CATALOG_WRITE_ROLES)),
):
    grade = db.query(NettingGrade).filter(NettingGrade.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Netting grade not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(grade, field, value)
    db.commit()
    db.refresh(grade)
    return grade
