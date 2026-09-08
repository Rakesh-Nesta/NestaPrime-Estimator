import math
import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, CostSheetStatus, WorkPackage
from app.models.project import Project, SoilType
from app.models.rate_item import LabourCategory, RateSource
from app.models.sport import ProjectSport, Sport

site_works_router = APIRouter(tags=["site-works"])

COST_ROLES = ("pm", "director")

FT_TO_M = 0.3048
SQFT_TO_SQM = 0.09290304
IN_TO_M = 0.0254
CONCRETE_WASTAGE_MULTIPLIER = 1.02  # J.3: "concrete cum = area_sqm x (thickness_in x 0.0254) x 1.02"

# J.3: "steel kg/cum by element (slab 80, footing 75, beam 120, column 160)"
# -- a base/sub-base is a slab, so 80 is the applicable default here.
STEEL_KG_PER_CUM_SLAB_DEFAULT = 80.0


def _labour_category(db: Session, key: str):
    return db.query(LabourCategory).filter(LabourCategory.key == key).first()


def _resolve_dimensions(
    db: Session, cost_sheet: CostSheet, project_sport_id: uuid.UUID, build_l_ft: float | None, build_w_ft: float | None
) -> tuple[float, float, ProjectSport]:
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
    L = build_l_ft if build_l_ft is not None else (float(sport.build_l_ft) if sport.build_l_ft else None)
    W = build_w_ft if build_w_ft is not None else (float(sport.build_w_ft) if sport.build_w_ft else None)
    if L is None or W is None:
        raise HTTPException(
            status_code=422, detail="build_l_ft/build_w_ft are required -- this sport has no default build dimensions"
        )
    return L, W, project_sport


_EDITABLE_COST_SHEET_STATUSES = (CostSheetStatus.DRAFT, CostSheetStatus.UNVERIFIED)


def _get_cost_sheet(db: Session, cost_sheet_id: uuid.UUID) -> CostSheet:
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status not in _EDITABLE_COST_SHEET_STATUSES:
        # M.1: an Unverified (skip-generated) cost sheet "behaves as Draft
        # for editing" -- lines can be added to either.
        raise HTTPException(status_code=400, detail="Lines can only be added to a Draft or Unverified cost sheet")
    return cost_sheet


# --------------------------------------------------------------------------
# D.1 Base / sub-base
# --------------------------------------------------------------------------


class BaseType(str, Enum):
    WBM = "wbm"
    ASPHALT = "asphalt"
    PCC = "pcc"
    RCC = "rcc"


class BaseTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    base_type: BaseType
    thickness_in: float = Field(gt=0)
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    material_rate_per_cum: float = Field(gt=0)
    steel_kg_per_cum: float = Field(default=STEEL_KG_PER_CUM_SLAB_DEFAULT, gt=0)  # RCC only
    steel_rate_per_kg: float | None = Field(default=None, gt=0)  # required if base_type == rcc


class BaseTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@site_works_router.post("/cost-sheets/{cost_sheet_id}/base", response_model=BaseTakeoffOut, status_code=201)
def add_base_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: BaseTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """D.1: 'the Cost Sheet prices base work from quantities (cum, kg) x
    material rates + labour activity rates, never from [the Rs/sqft sanity
    range] lump sums.' Volume formula is J.3's own: area_sqm x
    (thickness_in x 0.0254) x 1.02."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, project_sport = _resolve_dimensions(db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft)

    if payload.base_type == BaseType.RCC and payload.steel_rate_per_kg is None:
        raise HTTPException(status_code=422, detail="steel_rate_per_kg is required for an RCC base (reinforcement)")

    area_sqm = L * W * SQFT_TO_SQM
    thickness_m = payload.thickness_in * IN_TO_M
    volume_cum = area_sqm * thickness_m * CONCRETE_WASTAGE_MULTIPLIER

    civil_category = _labour_category(db, "civil_base_site_prep")

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.CIVIL,
            category="Base/sub-base",
            item_name=f"{payload.base_type.value.upper()} base {payload.thickness_in}in",
            unit="cum",
            quantity=round(volume_cum, 3),
            rate=payload.material_rate_per_cum,
            source=RateSource.MANUAL,
            labour_category_id=civil_category.id if civil_category else None,
            wastage_percent=round((CONCRETE_WASTAGE_MULTIPLIER - 1) * 100, 2),
        )
    ]

    steel_kg = None
    if payload.base_type == BaseType.RCC:
        steel_kg = volume_cum * payload.steel_kg_per_cum
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.CIVIL,
                category="Base reinforcement",
                item_name=f"Reinforcement steel @ {payload.steel_kg_per_cum}kg/cum",
                unit="kg",
                quantity=round(steel_kg, 2),
                rate=payload.steel_rate_per_kg,
                source=RateSource.MANUAL,
                labour_category_id=civil_category.id if civil_category else None,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return BaseTakeoffOut(
        breakdown={
            "area_sqm": round(area_sqm, 2),
            "volume_cum": round(volume_cum, 3),
            "steel_kg": round(steel_kg, 2) if steel_kg is not None else None,
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )


# --------------------------------------------------------------------------
# D.3 Drainage (mandatory outdoor)
# --------------------------------------------------------------------------

# D.3: pipe capacity table at 1:100 slope -- (max l/s, size mm), first match wins.
PIPE_CAPACITY_TABLE = [(8.0, 100), (20.0, 150), (50.0, 225)]

# D.3: "Sub-surface pipe spacing by soil permeability: sandy 8 m, normal
# 5 m, clay/black cotton 3 m c/c." Rocky and filled aren't given their own
# figure -- defaulted to "normal" spacing here, a documented approximation.
SOIL_SUBSURFACE_SPACING_M = {
    SoilType.SANDY: 8.0,
    SoilType.NORMAL: 5.0,
    SoilType.BLACK_COTTON: 3.0,
    SoilType.ROCKY: 5.0,
    SoilType.FILLED: 5.0,
}


def _pipe_size_mm(q_l_s: float) -> int | None:
    if q_l_s < 1.0:
        return None
    for capacity, size in PIPE_CAPACITY_TABLE:
        if q_l_s <= capacity:
            return size
    return None  # beyond the table -- needs an engineer, not this calculator


class DrainageTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    # D.3 rational method: C = 0.9 (turf/acrylic on WBM), 0.6 (natural grass).
    runoff_coefficient: float = Field(default=0.9, gt=0, le=1)
    rainfall_intensity_mm_per_hr: float = Field(gt=0)  # city design rainfall intensity, Master Settings per D.3
    high_rainfall: bool = False  # drives drain channel size label only (9x9in vs 12x12in)
    drain_rate_per_m: float = Field(gt=0)
    pipe_rate_per_m: float | None = Field(default=None, gt=0)  # required if Q >= 1 l/s
    catch_pit_rate_each: float = Field(gt=0)
    subsurface_turf_drainage: bool = False
    subsurface_pipe_rate_per_m: float | None = Field(default=None, gt=0)  # required if subsurface_turf_drainage


class DrainageTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@site_works_router.post("/cost-sheets/{cost_sheet_id}/drainage", response_model=DrainageTakeoffOut, status_code=201)
def add_drainage_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: DrainageTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """D.3: perimeter drain (mandatory outdoor) + pipe sized by the
    rational method (Q = 1000 x 0.278 x C x i x A) + catch pits (1 per
    50 ft of drain) + optional sub-surface turf drainage by soil
    permeability. Rainwater harvesting (D.3, 'where the scope item is
    ticked') is not implemented -- it depends on Part I's scope checklist
    state, a documented gap."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
    L, W, project_sport = _resolve_dimensions(db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft)

    perimeter_ft = 2 * (L + W)
    area_sqkm = (L * W * SQFT_TO_SQM) / 1_000_000
    q_l_s = 1000 * 0.278 * payload.runoff_coefficient * payload.rainfall_intensity_mm_per_hr * area_sqkm
    pipe_size_mm = _pipe_size_mm(q_l_s)
    catch_pits = math.ceil(perimeter_ft / 50)

    if pipe_size_mm is not None and payload.pipe_rate_per_m is None:
        raise HTTPException(
            status_code=422,
            detail=f"pipe_rate_per_m is required -- Q={round(q_l_s, 2)} l/s needs a {pipe_size_mm}mm pipe",
        )
    if payload.subsurface_turf_drainage and payload.subsurface_pipe_rate_per_m is None:
        raise HTTPException(status_code=422, detail="subsurface_pipe_rate_per_m is required for sub-surface turf drainage")

    civil_category = _labour_category(db, "civil_base_site_prep")
    perimeter_m = perimeter_ft * FT_TO_M
    drain_label = "12x12in RCC/brick channel (high rainfall)" if payload.high_rainfall else "9x9in RCC/brick channel"

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.CIVIL,
            category="Drainage",
            item_name=f"Perimeter drain -- {drain_label}",
            unit="m",
            quantity=round(perimeter_m, 2),
            rate=payload.drain_rate_per_m,
            source=RateSource.MANUAL,
            labour_category_id=civil_category.id if civil_category else None,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.CIVIL,
            category="Drainage",
            item_name="Catch pits (1 per 50 ft of drain)",
            unit="each",
            quantity=catch_pits,
            rate=payload.catch_pit_rate_each,
            source=RateSource.MANUAL,
            labour_category_id=civil_category.id if civil_category else None,
        ),
    ]

    if pipe_size_mm is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.CIVIL,
                category="Drainage",
                item_name=f"Drain pipe {pipe_size_mm}mm dia",
                unit="m",
                quantity=round(perimeter_m, 2),
                rate=payload.pipe_rate_per_m,
                source=RateSource.MANUAL,
                labour_category_id=civil_category.id if civil_category else None,
            )
        )

    subsurface_breakdown = None
    if payload.subsurface_turf_drainage:
        spacing_m = SOIL_SUBSURFACE_SPACING_M.get(project.soil_type, 5.0)
        runs = math.ceil((W * FT_TO_M) / spacing_m)
        subsurface_pipe_m = runs * (L * FT_TO_M)
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.CIVIL,
                category="Drainage",
                item_name=f"Sub-surface perforated pipe @ {spacing_m}m c/c ({project.soil_type.value})",
                unit="m",
                quantity=round(subsurface_pipe_m, 2),
                rate=payload.subsurface_pipe_rate_per_m,
                source=RateSource.MANUAL,
                labour_category_id=civil_category.id if civil_category else None,
            )
        )
        subsurface_breakdown = {"spacing_m": spacing_m, "runs": runs, "pipe_m": round(subsurface_pipe_m, 2)}

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return DrainageTakeoffOut(
        breakdown={
            "perimeter_m": round(perimeter_m, 2),
            "q_l_s": round(q_l_s, 3),
            "pipe_size_mm": pipe_size_mm,
            "catch_pits": catch_pits,
            "subsurface": subsurface_breakdown,
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
