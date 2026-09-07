import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet, _labour_category
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport

gym_router = APIRouter(tags=["gym"])

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


class GymZoneIn(BaseModel):
    zone_name: str = Field(min_length=1)  # e.g. "Cardio", "Strength", "Free weights", "Functional", "Studio"
    area_sqft: float = Field(gt=0)
    flooring_rate_per_sqft: float = Field(gt=0)


class GymEquipmentItemIn(BaseModel):
    item_name: str = Field(min_length=1)
    brand_tier: str | None = None  # free text -- G.2's own catalogue tiering, not the project's Budget/Standard/Premium package
    quantity: int = Field(gt=0)
    rate: float = Field(gt=0)


class GymTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    zones: list[GymZoneIn] = Field(default_factory=list)
    equipment: list[GymEquipmentItemIn] = Field(default_factory=list)
    # G.2's own "Inputs" column names this -- recorded for the record even
    # though no catalogue/formula is given anywhere to derive equipment
    # quantity from it, so it never drives a computation here.
    capacity_users_per_hour: int | None = Field(default=None, gt=0)
    electrical_point_rate: float | None = Field(default=None, gt=0)  # required if any equipment given


class GymTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@gym_router.post("/cost-sheets/{cost_sheet_id}/gym", response_model=GymTakeoffOut, status_code=201)
def add_gym_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: GymTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """G.2: Area (zones -> flooring per zone) and Equipment (list, priced
    as entered -- the blueprint says items come 'from catalogue' but
    gives no catalogue data or capacity->qty formula, so quantities are
    the PM's own, matching how J.1's Manual rate entry already works
    everywhere else in this app) are this module's own scope.

    Services are split across what already exists: HVAC and acoustic
    treatment run through the existing HVAC (G.5) tab on this same sport
    -- 'gymnasium' already carries G.5's own 20% acoustic coverage
    default. Lighting runs through the existing Lighting (H) tab at H's
    own stated 300 lux for gym. Only 'electrical points per machine' is
    computed here, literally: one point per equipment unit, summed across
    the whole equipment list. Mirrors, sound, reception, lockers and
    showers have no given formula or dimension and are better entered via
    the generic Manual line form than guessed at here."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    _get_project_sport(db, cost_sheet, payload.project_sport_id)

    if not payload.zones and not payload.equipment:
        raise HTTPException(status_code=422, detail="Provide at least one zone or one equipment item")

    total_equipment_qty = sum(item.quantity for item in payload.equipment)
    if payload.equipment and payload.electrical_point_rate is None:
        raise HTTPException(
            status_code=422, detail="electrical_point_rate is required when equipment items are given"
        )

    lines_to_create: list[CostSheetLine] = []
    zone_breakdowns = []
    for zone in payload.zones:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.FLOORING,
                category="Gym",
                item_name=f"{zone.zone_name} flooring",
                unit="sqft",
                quantity=zone.area_sqft,
                rate=zone.flooring_rate_per_sqft,
                source=RateSource.MANUAL,
            )
        )
        zone_breakdowns.append(
            {"zone_name": zone.zone_name, "area_sqft": zone.area_sqft, "amount": round(zone.area_sqft * zone.flooring_rate_per_sqft, 2)}
        )

    equipment_breakdowns = []
    for item in payload.equipment:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ACCESSORIES,
                category="Gym",
                item_name=f"{item.item_name} ({item.brand_tier})" if item.brand_tier else item.item_name,
                unit="nos",
                quantity=item.quantity,
                rate=item.rate,
                source=RateSource.MANUAL,
            )
        )
        equipment_breakdowns.append(
            {"item_name": item.item_name, "brand_tier": item.brand_tier, "quantity": item.quantity, "amount": round(item.quantity * item.rate, 2)}
        )

    if payload.equipment:
        electrical_category = _labour_category(db, "electrical")
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ELECTRICAL,
                category="Gym",
                item_name="Electrical points (1 per machine)",
                unit="point",
                quantity=total_equipment_qty,
                rate=payload.electrical_point_rate,
                source=RateSource.MANUAL,
                labour_category_id=electrical_category.id if electrical_category else None,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return GymTakeoffOut(
        breakdown={
            "zones": zone_breakdowns,
            "equipment": equipment_breakdowns,
            "total_equipment_qty": total_equipment_qty,
            "capacity_users_per_hour": payload.capacity_users_per_hour,
            "services_note": (
                "HVAC and acoustic treatment: use the existing HVAC (G.5) tab on this sport -- "
                "gymnasium already carries a 20% acoustic coverage default. "
                "Lighting: use the existing Lighting (H) tab at 300 lux (H's own gym figure). "
                "Mirrors, sound, reception, lockers, showers: no given formula -- add via Manual line."
            ),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
