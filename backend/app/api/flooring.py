import math
import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet, _labour_category, _resolve_dimensions
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport

flooring_router = APIRouter(tags=["flooring"])

COST_ROLES = ("pm", "director")


def _get_project_sport(db: Session, cost_sheet: CostSheet, project_sport_id: uuid.UUID) -> ProjectSport:
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    return project_sport

FT_TO_M = 0.3048
ROLL_LENGTH_M = 25.0
ROLL_WIDTHS_M = (4.0, 2.0)


class PileHeight(str, Enum):
    MM_30 = "30mm"
    MM_40 = "40mm"
    MM_50_FIFA_QUALITY = "50mm_fifa_quality"
    MM_50_60_FIFA_QUALITY_PRO = "50_60mm_fifa_quality_pro"
    PADEL_12MM = "padel_12mm"


# F.5: "Infill kg = area_sqm x (sand + rubber) by pile height [confirm]."
# FIFA Quality Pro's sand 25-30 / rubber 8-12 is a range in the blueprint;
# the midpoint is used here as the default, overridable per call.
INFILL_KG_PER_SQM = {
    PileHeight.MM_30: {"sand": 12.0, "rubber": 4.0},
    PileHeight.MM_40: {"sand": 18.0, "rubber": 7.0},
    PileHeight.MM_50_FIFA_QUALITY: {"sand": 22.0, "rubber": 9.0},
    PileHeight.MM_50_60_FIFA_QUALITY_PRO: {"sand": 27.5, "rubber": 10.0},
    PileHeight.PADEL_12MM: {"sand": 8.0, "rubber": 0.0},
}


def _best_turf_order(span_l_m: float, span_w_m: float, cut_length_allowed: bool) -> dict:
    """F.5: 'the app evaluates both lay directions x every available roll
    width x cut-length allowed yes/no and picks the minimum ordered sqm.'"""
    modes = ["cut", "whole"] if cut_length_allowed else ["whole"]
    best = None
    for roll_width_m in ROLL_WIDTHS_M:
        for span_across, span_along, orientation in (
            (span_w_m, span_l_m, "W-across"),
            (span_l_m, span_w_m, "L-across"),
        ):
            strips = math.ceil(span_across / roll_width_m)
            for mode in modes:
                if mode == "whole":
                    rolls_per_strip = math.ceil(span_along / ROLL_LENGTH_M)
                    ordered_sqm = strips * rolls_per_strip * roll_width_m * ROLL_LENGTH_M
                else:
                    ordered_sqm = strips * roll_width_m * span_along
                if best is None or ordered_sqm < best["ordered_sqm"]:
                    best = {
                        "roll_width_m": roll_width_m,
                        "orientation": orientation,
                        "mode": mode,
                        "strips": strips,
                        "ordered_sqm": ordered_sqm,
                    }
    return best


class TurfTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    pile_height: PileHeight
    cut_length_allowed: bool = True
    turf_rate_per_sqm: float = Field(gt=0)
    sand_rate_per_kg: float = Field(gt=0)
    rubber_rate_per_kg: float | None = Field(default=None, gt=0)  # required unless the pile height has no rubber
    sand_kg_per_sqm: float | None = Field(default=None, gt=0)  # override the F.5 table default
    rubber_kg_per_sqm: float | None = Field(default=None, ge=0)  # override the F.5 table default
    line_marking_sets: int = Field(default=0, ge=0)
    line_marking_rate_per_set: float | None = Field(default=None, gt=0)


class TurfTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@flooring_router.post(
    "/cost-sheets/{cost_sheet_id}/flooring/turf", response_model=TurfTakeoffOut, status_code=201
)
def add_turf_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: TurfTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """F.5: roll-layout optimisation (evaluates every roll width x lay
    direction x cut-length choice, orders the minimum sqm) and infill kg
    by pile height. Wooden flooring (F.3), acrylic/PU surfacing (F.2/F.3)
    and standalone line marking (F.6) each have their own take-off below;
    anything else in Part F still has no comparable formula and is better
    entered as a plain CostSheetLine (area x rate) via the generic
    /cost-sheets/{id}/lines endpoint than reimplemented here."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, project_sport = _resolve_dimensions(
        db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft
    )

    infill_defaults = INFILL_KG_PER_SQM[payload.pile_height]
    sand_kg_per_sqm = payload.sand_kg_per_sqm if payload.sand_kg_per_sqm is not None else infill_defaults["sand"]
    rubber_kg_per_sqm = (
        payload.rubber_kg_per_sqm if payload.rubber_kg_per_sqm is not None else infill_defaults["rubber"]
    )
    if rubber_kg_per_sqm > 0 and payload.rubber_rate_per_kg is None:
        raise HTTPException(status_code=422, detail="rubber_rate_per_kg is required for this pile height's infill")
    if payload.line_marking_sets > 0 and payload.line_marking_rate_per_set is None:
        raise HTTPException(status_code=422, detail="line_marking_rate_per_set is required when line_marking_sets > 0")

    L_m, W_m = L * FT_TO_M, W * FT_TO_M
    build_area_sqm = L_m * W_m
    best = _best_turf_order(L_m, W_m, payload.cut_length_allowed)
    wastage_percent = (best["ordered_sqm"] - build_area_sqm) / build_area_sqm * 100

    turf_category = _labour_category(db, "turf_laying")

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Turf",
            item_name=(
                f"Turf roll {best['roll_width_m']:g}m wide, {best['mode']} ({best['orientation']}) -- "
                f"{payload.pile_height.value}"
            ),
            unit="sqm",
            quantity=round(best["ordered_sqm"], 2),
            rate=payload.turf_rate_per_sqm,
            source=RateSource.MANUAL,
            labour_category_id=turf_category.id if turf_category else None,
            wastage_percent=round(wastage_percent, 2),
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Infill",
            item_name=f"Sand infill @ {sand_kg_per_sqm}kg/sqm",
            unit="kg",
            quantity=round(build_area_sqm * sand_kg_per_sqm, 2),
            rate=payload.sand_rate_per_kg,
            source=RateSource.MANUAL,
            labour_category_id=turf_category.id if turf_category else None,
        ),
    ]

    if rubber_kg_per_sqm > 0:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Infill",
                item_name=f"Rubber infill @ {rubber_kg_per_sqm}kg/sqm",
                unit="kg",
                quantity=round(build_area_sqm * rubber_kg_per_sqm, 2),
                rate=payload.rubber_rate_per_kg,
                source=RateSource.MANUAL,
                labour_category_id=turf_category.id if turf_category else None,
            )
        )

    if payload.line_marking_sets > 0:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Line marking",
                item_name="Inlaid line marking",
                unit="set",
                quantity=payload.line_marking_sets,
                rate=payload.line_marking_rate_per_set,
                source=RateSource.MANUAL,
                labour_category_id=turf_category.id if turf_category else None,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return TurfTakeoffOut(
        breakdown={
            "build_area_sqm": round(build_area_sqm, 4),
            "roll_width_m": best["roll_width_m"],
            "orientation": best["orientation"],
            "mode": best["mode"],
            "strips": best["strips"],
            "ordered_sqm": round(best["ordered_sqm"], 2),
            "wastage_percent": round(wastage_percent, 2),
            "sand_kg": round(build_area_sqm * sand_kg_per_sqm, 2),
            "rubber_kg": round(build_area_sqm * rubber_kg_per_sqm, 2),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )


# ---------------------------------------------------------------------------
# F.3 Indoor wooden flooring layer system
# ---------------------------------------------------------------------------


class WoodenFlooringTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    hardwood_rate_per_sqft: float = Field(gt=0)
    include_ply: bool = True
    ply_rate_per_sqft: float | None = Field(default=None, gt=0)
    include_battens: bool = True
    battens_rate_per_sqft: float | None = Field(default=None, gt=0)
    include_moisture_barrier: bool = True
    moisture_barrier_rate_per_sqft: float | None = Field(default=None, gt=0)


class WoodenFlooringTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@flooring_router.post(
    "/cost-sheets/{cost_sheet_id}/flooring/wooden", response_model=WoodenFlooringTakeoffOut, status_code=201
)
def add_wooden_flooring_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: WoodenFlooringTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """F.3: 'hardwood 22 mm T&G -> 12 mm ply -> battens/cradles with
    rubber pads (the sprung layer) -> moisture barrier (DPM)' -- the base
    below that (PCC/RCC/compacted stone) is the existing Base (D.1)
    take-off's job, run separately. Each layer covers the same footprint,
    so one L x W input fans out into up to four correctly tagged lines
    instead of the PM re-typing the same area four times (and forgetting
    one, per the app's own founding pain point).

    Only the hardwood line carries labour_category_id=wooden_flooring
    with unit sqft, so it alone can pick up J.2's activity rate; the
    supporting layers carry no labour_category_id and use the blended
    fallback, so the one installation isn't billed the activity rate
    four times over."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, _project_sport = _resolve_dimensions(
        db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft
    )
    area_sqft = L * W

    if payload.include_ply and payload.ply_rate_per_sqft is None:
        raise HTTPException(status_code=422, detail="ply_rate_per_sqft is required when include_ply is true")
    if payload.include_battens and payload.battens_rate_per_sqft is None:
        raise HTTPException(status_code=422, detail="battens_rate_per_sqft is required when include_battens is true")
    if payload.include_moisture_barrier and payload.moisture_barrier_rate_per_sqft is None:
        raise HTTPException(
            status_code=422, detail="moisture_barrier_rate_per_sqft is required when include_moisture_barrier is true"
        )

    wooden_category = _labour_category(db, "wooden_flooring")

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Wooden flooring",
            item_name="Hardwood 22mm T&G",
            unit="sqft",
            quantity=round(area_sqft, 2),
            rate=payload.hardwood_rate_per_sqft,
            source=RateSource.MANUAL,
            labour_category_id=wooden_category.id if wooden_category else None,
        )
    ]
    if payload.include_ply:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Wooden flooring",
                item_name="12mm plywood underlayer",
                unit="sqft",
                quantity=round(area_sqft, 2),
                rate=payload.ply_rate_per_sqft,
                source=RateSource.MANUAL,
            )
        )
    if payload.include_battens:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Wooden flooring",
                item_name="Battens/cradles with rubber pads (sprung layer)",
                unit="sqft",
                quantity=round(area_sqft, 2),
                rate=payload.battens_rate_per_sqft,
                source=RateSource.MANUAL,
            )
        )
    if payload.include_moisture_barrier:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Wooden flooring",
                item_name="Moisture barrier (DPM)",
                unit="sqft",
                quantity=round(area_sqft, 2),
                rate=payload.moisture_barrier_rate_per_sqft,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return WoodenFlooringTakeoffOut(
        breakdown={"area_sqft": round(area_sqft, 2), "layers": len(lines_to_create)},
        lines=[_line_to_out(line) for line in lines_to_create],
    )


# ---------------------------------------------------------------------------
# F.2/F.3 Acrylic / PU surfacing
# ---------------------------------------------------------------------------


class SurfaceType(str, Enum):
    ACRYLIC = "acrylic"
    PU = "pu"


class AcrylicPuTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    surface_type: SurfaceType
    coats: int = Field(default=1, ge=1)  # F.2: acrylic "5-8 coats"; PU is a single applied system, coats=1
    rate_per_sqft_per_coat: float = Field(gt=0)


class AcrylicPuTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@flooring_router.post(
    "/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu", response_model=AcrylicPuTakeoffOut, status_code=201
)
def add_acrylic_pu_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: AcrylicPuTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """F.2/F.3: acrylic is applied in multiple coats ('5-8 coats'), so
    quantity is area_sqft x coats -- one extra coat is exactly one more
    unit of labour and material, which J.2's 'Rs/sqft acrylic (per coat)'
    activity rate is written to price directly. The sub-base under this
    (asphalt/WBM/PCC) is the existing Base (D.1) take-off's job, run
    separately."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, _project_sport = _resolve_dimensions(
        db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft
    )
    area_sqft = L * W
    quantity_sqft_coats = area_sqft * payload.coats

    acrylic_pu_category = _labour_category(db, "acrylic_pu")
    label = "Acrylic" if payload.surface_type == SurfaceType.ACRYLIC else "PU"

    line = CostSheetLine(
        cost_sheet_id=cost_sheet_id,
        project_sport_id=payload.project_sport_id,
        work_package=WorkPackage.FLOORING,
        category="Acrylic/PU surfacing",
        item_name=f"{label} surfacing ({payload.coats} coat{'s' if payload.coats != 1 else ''})",
        unit="sqft",
        quantity=round(quantity_sqft_coats, 2),
        rate=payload.rate_per_sqft_per_coat,
        source=RateSource.MANUAL,
        labour_category_id=acrylic_pu_category.id if acrylic_pu_category else None,
    )
    db.add(line)
    db.commit()
    db.refresh(line)

    return AcrylicPuTakeoffOut(
        breakdown={"area_sqft": round(area_sqft, 2), "coats": payload.coats, "quantity_sqft_coats": round(quantity_sqft_coats, 2)},
        lines=[_line_to_out(line)],
    )


# ---------------------------------------------------------------------------
# F.6 Line-marking sets (standalone -- for any flooring type; turf's own
# take-off keeps its inline single-set field for the common single-sport
# case, this covers multipurpose courts with several named sets)
# ---------------------------------------------------------------------------


class LineMarkingStyle(str, Enum):
    INLAID = "inlaid"  # turf
    PAINTED = "painted"  # acrylic/hard courts


class LineMarkingSetIn(BaseModel):
    sport_label: str = Field(min_length=1)  # e.g. "Basketball (white)"
    style: LineMarkingStyle
    rate_per_set: float = Field(gt=0)


class LineMarkingTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    sets: list[LineMarkingSetIn] = Field(min_length=1, max_length=4)  # F.6: "Multipurpose ... up to 4"


class LineMarkingTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@flooring_router.post(
    "/cost-sheets/{cost_sheet_id}/flooring/line-marking", response_model=LineMarkingTakeoffOut, status_code=201
)
def add_line_marking_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: LineMarkingTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """F.6: 'Multipurpose: up to 4 [sets] ... per sport' -- one set per
    sport sharing a court, each independently priced and styled (inlaid
    for turf, painted for acrylic/hard courts)."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    _get_project_sport(db, cost_sheet, payload.project_sport_id)

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Line marking",
            item_name=f"{s.sport_label} line marking ({s.style.value})",
            unit="set",
            quantity=1,
            rate=s.rate_per_set,
            source=RateSource.MANUAL,
        )
        for s in payload.sets
    ]
    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return LineMarkingTakeoffOut(
        breakdown={"sets": len(lines_to_create)},
        lines=[_line_to_out(line) for line in lines_to_create],
    )


# ---------------------------------------------------------------------------
# F.4 Natural grass & irrigation
# ---------------------------------------------------------------------------

SPRINKLER_GRID_SPACING_M_DEFAULT = 12.0  # F.4: "pop-up sprinklers grid 12 m"
HOCKEY_CANNON_COUNT_DEFAULT = 6  # F.4: "Hockey water-based turf: sprinkler cannons x6"
NATURAL_GRASS_TOPSOIL_THICKNESS_IN = 6.0  # F.4: "Topsoil 6in + sand amendment"


class NaturalGrassCoverType(str, Enum):
    SOD = "sod"
    SEED = "seed"  # F.4: "(or seed, 6-8 wks)"


class NaturalGrassTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    topsoil_rate_per_cum: float = Field(gt=0)  # F.4: "Topsoil 6in + sand amendment" -- one combined line
    cover_type: NaturalGrassCoverType = NaturalGrassCoverType.SOD
    cover_rate_per_sqm: float = Field(gt=0)
    sprinkler_spacing_m: float = Field(default=SPRINKLER_GRID_SPACING_M_DEFAULT, gt=0)
    sprinkler_rate_each: float = Field(gt=0)
    pump_rate: float = Field(gt=0)  # lump sum
    tank_rate: float = Field(gt=0)  # F.4's own fixed spec: "10,000 L tank"


class NaturalGrassTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@flooring_router.post(
    "/cost-sheets/{cost_sheet_id}/flooring/natural-grass", response_model=NaturalGrassTakeoffOut, status_code=201
)
def add_natural_grass_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: NaturalGrassTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """F.4: 'Topsoil 6in + sand amendment -> sod (or seed, 6-8 wks) ->
    pop-up sprinklers grid 12m -> pump + 10,000L tank -> monthly
    maintenance note.' Sprinkler count follows the same spacing-grid
    logic as every other grid take-off in this app (D.3's catch pits,
    H's fixture count): one sprinkler per 12m x 12m cell, ceil'd per
    axis. The 10,000L tank is F.4's own fixed spec for this system, not
    scaled by area -- a single lump line, same as the pump. Monthly
    maintenance is a recurring O&M cost, not a one-time Cost Sheet item,
    so it's noted, not priced (AMC already has its own home in Part I's
    scope checklist)."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, _project_sport = _resolve_dimensions(
        db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft
    )
    L_m, W_m = L * FT_TO_M, W * FT_TO_M
    area_sqm = L_m * W_m

    topsoil_thickness_m = NATURAL_GRASS_TOPSOIL_THICKNESS_IN * 0.0254
    topsoil_volume_cum = area_sqm * topsoil_thickness_m

    sprinkler_count = math.ceil(L_m / payload.sprinkler_spacing_m) * math.ceil(W_m / payload.sprinkler_spacing_m)

    cover_label = "Sod" if payload.cover_type == NaturalGrassCoverType.SOD else "Seed (6-8 week germination)"

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Natural grass",
            item_name=f"Topsoil ({NATURAL_GRASS_TOPSOIL_THICKNESS_IN:g}in) + sand amendment",
            unit="cum",
            quantity=round(topsoil_volume_cum, 3),
            rate=payload.topsoil_rate_per_cum,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Natural grass",
            item_name=cover_label,
            unit="sqm",
            quantity=round(area_sqm, 2),
            rate=payload.cover_rate_per_sqm,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Irrigation",
            item_name=f"Pop-up sprinklers @ {payload.sprinkler_spacing_m:g}m grid",
            unit="nos",
            quantity=sprinkler_count,
            rate=payload.sprinkler_rate_each,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Irrigation",
            item_name="Irrigation pump",
            unit="set",
            quantity=1,
            rate=payload.pump_rate,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Irrigation",
            item_name="Water tank (10,000 L)",
            unit="set",
            quantity=1,
            rate=payload.tank_rate,
            source=RateSource.MANUAL,
        ),
    ]

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return NaturalGrassTakeoffOut(
        breakdown={
            "area_sqm": round(area_sqm, 2),
            "topsoil_volume_cum": round(topsoil_volume_cum, 3),
            "sprinkler_count": sprinkler_count,
            "maintenance_note": (
                "F.4: monthly maintenance (mowing, feeding) is a recurring cost, not priced on this "
                "one-time Cost Sheet -- track it under AMC (Part I's maintenance scope group) instead."
            ),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )


class HockeyIrrigationTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    cannon_count: int = Field(default=HOCKEY_CANNON_COUNT_DEFAULT, gt=0)
    cannon_rate_each: float = Field(gt=0)
    pump_rate: float = Field(gt=0)
    tank_rate: float = Field(gt=0)  # F.4's own fixed spec: "50,000L tank"


class HockeyIrrigationTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@flooring_router.post(
    "/cost-sheets/{cost_sheet_id}/flooring/hockey-irrigation",
    response_model=HockeyIrrigationTakeoffOut,
    status_code=201,
)
def add_hockey_irrigation_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: HockeyIrrigationTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """F.4: 'Hockey water-based turf: sprinkler cannons x6 + 50,000L tank
    + pump.' This wets the synthetic FIH pitch for ball speed -- a
    different, much larger system than natural grass irrigation, not a
    variant of it, so it's its own endpoint rather than a branch on the
    natural-grass one. cannon_count defaults to F.4's own '6' but stays
    overridable, same as every other blueprint-given default in this app."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Irrigation",
            item_name="Sprinkler cannon",
            unit="nos",
            quantity=payload.cannon_count,
            rate=payload.cannon_rate_each,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Irrigation",
            item_name="Irrigation pump",
            unit="set",
            quantity=1,
            rate=payload.pump_rate,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.FLOORING,
            category="Irrigation",
            item_name="Water tank (50,000 L)",
            unit="set",
            quantity=1,
            rate=payload.tank_rate,
            source=RateSource.MANUAL,
        ),
    ]

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return HockeyIrrigationTakeoffOut(
        breakdown={"cannon_count": payload.cannon_count},
        lines=[_line_to_out(line) for line in lines_to_create],
    )
