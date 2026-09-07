import math
import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet, _resolve_dimensions
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import Sport

hvac_router = APIRouter(tags=["hvac"])

COST_ROLES = ("pm", "director")

SQFT_TO_SQM = 0.09290304
HVAC_ENGINEER_CONFIRMATION_TR_THRESHOLD = 40.0
FRESH_AIR_CFM_PER_PERSON = 15  # G.5: "fresh air 15 CFM/person"


class ClimateZone(str, Enum):
    HOT_HUMID = "hot_humid"
    HOT_DRY = "hot_dry"
    MODERATE = "moderate"
    COLD = "cold"


CLIMATE_FACTOR = {
    ClimateZone.HOT_HUMID: 1.3,
    ClimateZone.HOT_DRY: 1.2,
    ClimateZone.MODERATE: 1.0,
    ClimateZone.COLD: 0.8,
}

# G.5: "Acoustic panel area = wall_area x coverage %" -- squash 40%,
# badminton 25%, TT 25%, gym 20%. No coverage % is given for any other
# sport, so those require an explicit override rather than a guess.
ACOUSTIC_COVERAGE_PERCENT_BY_SPORT_KEY = {
    "squash": 40.0,
    "badminton": 25.0,
    "table_tennis": 25.0,
    "gymnasium": 20.0,
}


def _height_factor(height_ft: float) -> float:
    if height_ft <= 16:
        return 1.0
    if height_ft <= 24:
        return 1.2
    return 1.4


class HvacTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    height_ft: float = Field(gt=0)
    climate: ClimateZone
    ac_rate_per_tr: float = Field(gt=0)
    ducting_rate_per_sqft: float = Field(gt=0)
    occupancy: int | None = Field(default=None, ge=1)  # for the fresh-air CFM figure
    fresh_air_unit_rate: float | None = Field(default=None, gt=0)  # optional cost line, Rs per CFM
    coverage_percent: float | None = Field(default=None, gt=0, le=100)  # overrides the sport lookup
    acoustic_panel_rate_per_sqm: float | None = Field(default=None, gt=0)


class HvacTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@hvac_router.post("/cost-sheets/{cost_sheet_id}/hvac", response_model=HvacTakeoffOut, status_code=201)
def add_hvac_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: HvacTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """G.5: tonnage = (area_sqft / 130) x climate_factor x height_factor,
    rounded up to the next whole TR. Ducting is priced Rs/sqft of floor;
    fresh air (15 CFM/person) and acoustic panel area (wall_area x
    sport-specific coverage %) are each optional add-ons, only priced when
    their rate is supplied. J.2's labour-category table names no HVAC
    activity or fallback %, so HVAC lines carry no labour_category_id and
    use the blended 22% fallback -- a documented gap in the blueprint
    itself, not this implementation."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, project_sport = _resolve_dimensions(
        db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft
    )
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()

    floor_area_sqft = L * W  # G.5's own formula is stated in sqft, unlike this app's usual sqm convention
    climate_factor = CLIMATE_FACTOR[payload.climate]
    height_factor = _height_factor(payload.height_ft)
    tonnage_raw = (floor_area_sqft / 130) * climate_factor * height_factor
    tonnage_tr = math.ceil(tonnage_raw)
    engineer_confirmation_required = tonnage_tr > HVAC_ENGINEER_CONFIRMATION_TR_THRESHOLD

    fresh_air_cfm = payload.occupancy * FRESH_AIR_CFM_PER_PERSON if payload.occupancy else None
    if payload.fresh_air_unit_rate is not None and fresh_air_cfm is None:
        raise HTTPException(status_code=422, detail="occupancy is required to price a fresh-air line")

    coverage_percent = payload.coverage_percent
    if coverage_percent is None:
        coverage_percent = ACOUSTIC_COVERAGE_PERCENT_BY_SPORT_KEY.get(sport.key)
    if payload.acoustic_panel_rate_per_sqm is not None and coverage_percent is None:
        raise HTTPException(
            status_code=422,
            detail=f"coverage_percent is required -- {sport.name} has no G.5 coverage default",
        )
    acoustic_panel_area_sqm = None
    if coverage_percent is not None:
        wall_area_sqft = 2 * (L + W) * payload.height_ft
        acoustic_panel_area_sqft = wall_area_sqft * coverage_percent / 100
        acoustic_panel_area_sqm = acoustic_panel_area_sqft * SQFT_TO_SQM

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.HVAC,
            category="HVAC",
            item_name=f"AC unit capacity ({payload.climate.value}, {payload.height_ft:g}ft height)",
            unit="TR",
            quantity=tonnage_tr,
            rate=payload.ac_rate_per_tr,
            source=RateSource.MANUAL,
        ),
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.HVAC,
            category="HVAC",
            item_name="Ducting",
            unit="sqft",
            quantity=round(floor_area_sqft, 2),
            rate=payload.ducting_rate_per_sqft,
            source=RateSource.MANUAL,
        ),
    ]

    if fresh_air_cfm is not None and payload.fresh_air_unit_rate is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.HVAC,
                category="HVAC",
                item_name="Fresh air handling",
                unit="cfm",
                quantity=fresh_air_cfm,
                rate=payload.fresh_air_unit_rate,
                source=RateSource.MANUAL,
            )
        )

    if acoustic_panel_area_sqm is not None and payload.acoustic_panel_rate_per_sqm is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.HVAC,
                category="Acoustic treatment",
                item_name=f"Acoustic panels ({coverage_percent:g}% wall coverage)",
                unit="sqm",
                quantity=round(acoustic_panel_area_sqm, 2),
                rate=payload.acoustic_panel_rate_per_sqm,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return HvacTakeoffOut(
        breakdown={
            "floor_area_sqft": round(floor_area_sqft, 2),
            "climate_factor": climate_factor,
            "height_factor": height_factor,
            "tonnage_raw": round(tonnage_raw, 2),
            "tonnage_tr": tonnage_tr,
            "engineer_confirmation_required": engineer_confirmation_required,
            "fresh_air_cfm": fresh_air_cfm,
            "coverage_percent": coverage_percent,
            "acoustic_panel_area_sqm": round(acoustic_panel_area_sqm, 2) if acoustic_panel_area_sqm is not None else None,
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
