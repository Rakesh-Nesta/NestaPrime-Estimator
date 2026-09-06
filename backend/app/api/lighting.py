import math
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet, _labour_category, _resolve_dimensions
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import Sport, SportCategory

lighting_router = APIRouter(tags=["lighting"])

COST_ROLES = ("pm", "director")

FT_TO_M = 0.3048
SQFT_TO_SQM = 0.09290304

# H: "UF 0.6 outdoor / 0.7 indoor; MF 0.8 indoor, 0.7 outdoor."
UF_BY_CATEGORY = {SportCategory.OUTDOOR: 0.6, SportCategory.INDOOR: 0.7}
MF_BY_CATEGORY = {SportCategory.OUTDOOR: 0.7, SportCategory.INDOOR: 0.8}

RUNNING_HOURS_DAYS_PER_MONTH = 30


class LightingTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    build_l_ft: float | None = None
    build_w_ft: float | None = None
    lux: float = Field(gt=0)  # target illuminance, H's own lux-level table (practice/match/tournament)
    lumens_per_fixture: float = Field(gt=0)
    wattage_per_fixture: float = Field(gt=0)
    fixture_rate_each: float = Field(gt=0)
    # H: mounting follows the structure (B.1a) -- Types A/B/C/E mount on
    # columns/trusses (no poles); open air/Type D/Type G use poles. Not
    # auto-derived from a stored structure choice (none is persisted yet);
    # the caller states it directly, same as Structures' own inputs.
    uses_poles: bool = False
    pole_count: int | None = Field(default=None, ge=1)
    pole_height_m: float | None = Field(default=None, gt=0)
    cable_length_m: float | None = Field(default=None, gt=0)
    cable_rate_per_m: float | None = Field(default=None, gt=0)
    mcb_panel_rate: float | None = Field(default=None, gt=0)
    earthing_rate: float | None = Field(default=None, gt=0)
    lightning_arrestor_rate: float | None = Field(default=None, gt=0)
    # Informational only (not a Cost Sheet line -- this is an OPEX estimate,
    # the Cost Sheet is CAPEX): monthly running cost at city tariff.
    tariff_rate_per_kwh: float | None = Field(default=None, gt=0)
    hours_per_day: float | None = Field(default=None, gt=0)


class LightingTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@lighting_router.post("/cost-sheets/{cost_sheet_id}/lighting", response_model=LightingTakeoffOut, status_code=201)
def add_lighting_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: LightingTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """H: fixtures = ceil((area_sqm x lux) / (lumens_per_fixture x UF x MF)).
    When poles are used, the final count is max(formula result, poles x 1),
    rounded up to an even number so every pole carries at least one
    fixture. Cabling / MCB panel / earthing / lightning arrestor (only
    required above 10 m pole height) are each optional add-on lines."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    L, W, project_sport = _resolve_dimensions(
        db, cost_sheet, payload.project_sport_id, payload.build_l_ft, payload.build_w_ft
    )
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()

    if payload.uses_poles and payload.pole_count is None:
        raise HTTPException(status_code=422, detail="pole_count is required when uses_poles is true")
    needs_lightning_arrestor = payload.uses_poles and payload.pole_height_m is not None and payload.pole_height_m > 10
    if needs_lightning_arrestor and payload.lightning_arrestor_rate is None:
        raise HTTPException(
            status_code=422, detail="lightning_arrestor_rate is required -- pole height exceeds 10 m (E.5/H)"
        )

    uf = UF_BY_CATEGORY[sport.category]
    mf = MF_BY_CATEGORY[sport.category]
    area_sqm = L * W * SQFT_TO_SQM
    raw_fixtures = (area_sqm * payload.lux) / (payload.lumens_per_fixture * uf * mf)
    fixtures_by_formula = math.ceil(raw_fixtures)

    if payload.uses_poles:
        fixture_count = max(fixtures_by_formula, payload.pole_count)
        if fixture_count % 2 != 0:
            fixture_count += 1
    else:
        fixture_count = fixtures_by_formula

    total_kw = fixture_count * payload.wattage_per_fixture / 1000
    monthly_running_cost = None
    if payload.tariff_rate_per_kwh is not None and payload.hours_per_day is not None:
        monthly_running_cost = total_kw * payload.hours_per_day * RUNNING_HOURS_DAYS_PER_MONTH * payload.tariff_rate_per_kwh

    electrical_category = _labour_category(db, "electrical")

    lines_to_create = [
        CostSheetLine(
            cost_sheet_id=cost_sheet_id,
            project_sport_id=payload.project_sport_id,
            work_package=WorkPackage.ELECTRICAL,
            category="Lighting fixtures",
            item_name=f"Lighting fixture, {payload.wattage_per_fixture:g}W ({payload.lumens_per_fixture:g}lm)",
            unit="each",
            quantity=fixture_count,
            rate=payload.fixture_rate_each,
            source=RateSource.MANUAL,
            labour_category_id=electrical_category.id if electrical_category else None,
        )
    ]

    if payload.cable_length_m is not None and payload.cable_rate_per_m is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ELECTRICAL,
                category="Lighting",
                item_name="Lighting cabling",
                unit="m",
                quantity=payload.cable_length_m,
                rate=payload.cable_rate_per_m,
                source=RateSource.MANUAL,
                labour_category_id=electrical_category.id if electrical_category else None,
            )
        )

    if payload.mcb_panel_rate is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ELECTRICAL,
                category="Lighting",
                item_name="MCB panel",
                unit="lot",
                quantity=1,
                rate=payload.mcb_panel_rate,
                source=RateSource.MANUAL,
                labour_category_id=electrical_category.id if electrical_category else None,
            )
        )

    if payload.earthing_rate is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ELECTRICAL,
                category="Lighting",
                item_name="Earthing",
                unit="lot",
                quantity=1,
                rate=payload.earthing_rate,
                source=RateSource.MANUAL,
                labour_category_id=electrical_category.id if electrical_category else None,
            )
        )

    if needs_lightning_arrestor:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ELECTRICAL,
                category="Lighting",
                item_name="Lightning arrestor",
                unit="each",
                quantity=1,
                rate=payload.lightning_arrestor_rate,
                source=RateSource.MANUAL,
                labour_category_id=electrical_category.id if electrical_category else None,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return LightingTakeoffOut(
        breakdown={
            "area_sqm": round(area_sqm, 2),
            "uf": uf,
            "mf": mf,
            "fixtures_by_formula": fixtures_by_formula,
            "fixture_count": fixture_count,
            "total_kw": round(total_kw, 2),
            "monthly_running_cost_estimate": round(monthly_running_cost, 2) if monthly_running_cost is not None else None,
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
