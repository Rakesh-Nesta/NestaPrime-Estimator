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
from app.models.document import CostSheetLine, WorkPackage
from app.models.rate_item import RateSource

flooring_router = APIRouter(tags=["flooring"])

COST_ROLES = ("pm", "director")

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
    by pile height. Everything else in Part F -- indoor/outdoor flooring
    other than turf, line-marking sets on their own -- has no comparable
    formula and is better entered as a plain CostSheetLine (area x rate)
    via the generic /cost-sheets/{id}/lines endpoint than reimplemented
    here."""
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
