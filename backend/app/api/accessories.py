import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport, Sport

accessories_router = APIRouter(tags=["accessories"])

COST_ROLES = ("pm", "director")

# Part I / Module 9: "Accessories (auto per sport): goals, nets, posts,
# scoreboards, stumps, umpire chairs, lane ropes, starting blocks, glass
# doors (padel), padel nets, pickleball nets, archery targets." The
# blueprint names the item *types* but gives no per-sport quantity table,
# so this catalog is this implementation's own working default: one row
# per (item_name, unit, quantity per court/lane) for sports where the
# equipment is near-universal. Optional extras (scoreboard, umpire chair)
# are deliberately left out of the fixed catalog since they aren't always
# wanted -- they go through custom_items below, same as any sport with no
# catalog entry at all. Swimming pool and gym/play equipment are out of
# scope (Parts G.1/G.2/G.4 aren't built), so lane ropes and gym/play
# equipment are not catalogued either.
ACCESSORY_CATALOG: dict[str, list[tuple[str, str, float]]] = {
    "badminton": [("Badminton net + post set", "set", 1)],
    "table_tennis": [("Table tennis net + post set", "set", 1)],
    "basketball_indoor": [("Basketball goal (backboard + ring)", "nos", 2)],
    "basketball_outdoor": [("Basketball goal (backboard + ring)", "nos", 2)],
    "volleyball_indoor": [("Volleyball net + post set", "set", 1)],
    "volleyball_outdoor": [("Volleyball net + post set", "set", 1)],
    "beach_volleyball": [("Volleyball net + post set", "set", 1)],
    "indoor_cricket_nets": [("Cricket stumps set (2 ends)", "set", 1)],
    "cricket_practice_nets": [("Cricket stumps set (2 ends)", "set", 1)],
    "box_cricket": [("Cricket stumps set (2 ends)", "set", 1)],
    "football_11": [("Football goal with net", "nos", 2)],
    "football_7": [("Football goal with net", "nos", 2)],
    "football_5_futsal": [("Football goal with net", "nos", 2)],
    "tennis": [("Tennis net + post set", "set", 1)],
    "padel": [("Padel glass wall/door panel set", "set", 1), ("Padel net", "nos", 1)],
    "pickleball": [("Pickleball net + post set", "set", 1)],
    "hockey_turf": [("Hockey goal with net", "nos", 2)],
    "athletic_track_400m": [("Starting block", "nos", 8)],  # seed name is "400 m, 8 lane"
    "archery_range": [("Archery target (butt/boss)", "nos", 1)],
}


class CustomAccessoryLine(BaseModel):
    item_name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    rate: float = Field(gt=0)


class AccessoryTakeoffRequest(BaseModel):
    project_sport_id: uuid.UUID
    rates: dict[str, float] = Field(default_factory=dict)  # catalog item_name -> Rs per unit
    custom_items: list[CustomAccessoryLine] = Field(default_factory=list)


class AccessoryTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


def _get_project_sport(db: Session, cost_sheet, project_sport_id: uuid.UUID) -> ProjectSport:
    project_sport = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == project_sport_id, ProjectSport.project_id == cost_sheet.project_id)
        .first()
    )
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not on this project")
    return project_sport


@accessories_router.post(
    "/cost-sheets/{cost_sheet_id}/accessories", response_model=AccessoryTakeoffOut, status_code=201
)
def add_accessories_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: AccessoryTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """Part I / Module 9: catalog quantities scale with the sport
    selection's own number_of_courts (Module 1) -- 2 basketball goals per
    court, 8 starting blocks per 400m track, and so on. A sport with no
    catalog entry, or an extra item a catalog doesn't cover, must be
    named explicitly via custom_items rather than guessed. J.2's labour
    table has no accessories row, so these lines carry no
    labour_category_id and fall back to the blended 22%, the same
    documented gap as HVAC (G.5)."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    project_sport = _get_project_sport(db, cost_sheet, payload.project_sport_id)
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()

    catalog_items = ACCESSORY_CATALOG.get(sport.key, [])
    if not catalog_items and not payload.custom_items:
        raise HTTPException(
            status_code=422,
            detail=f"No accessories catalog for {sport.name} -- specify custom_items",
        )

    missing_rates = [name for name, _unit, _qty in catalog_items if name not in payload.rates]
    if missing_rates:
        raise HTTPException(status_code=422, detail=f"Missing rate for: {', '.join(missing_rates)}")

    lines_to_create: list[CostSheetLine] = []
    applied = []
    for item_name, unit, qty_per_court in catalog_items:
        quantity = qty_per_court * project_sport.number_of_courts
        rate = payload.rates[item_name]
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ACCESSORIES,
                category="Accessories",
                item_name=item_name,
                unit=unit,
                quantity=quantity,
                rate=rate,
                source=RateSource.MANUAL,
            )
        )
        applied.append({"item_name": item_name, "unit": unit, "quantity": quantity, "rate": rate})

    for custom in payload.custom_items:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ACCESSORIES,
                category="Accessories",
                item_name=custom.item_name,
                unit=custom.unit,
                quantity=custom.quantity,
                rate=custom.rate,
                source=RateSource.MANUAL,
            )
        )

    db.add_all(lines_to_create)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return AccessoryTakeoffOut(
        breakdown={
            "sport_key": sport.key,
            "number_of_courts": project_sport.number_of_courts,
            "catalog_items_applied": applied,
            "custom_items_count": len(payload.custom_items),
        },
        lines=[_line_to_out(line) for line in lines_to_create],
    )
