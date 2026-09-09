import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.accessory_catalog_item import AccessoryCatalogItem
from app.models.document import CostSheetLine, WorkPackage
from app.models.rate_item import RateSource
from app.models.sport import ProjectSport, Sport

accessories_router = APIRouter(tags=["accessories"])
accessory_catalog_router = APIRouter(prefix="/accessory-catalog", tags=["accessory-catalog"])

COST_ROLES = ("pm", "director")
# The catalog itself carries no Rs figures (item + quantity only, no
# rate) -- K.3's cost-visibility gate doesn't apply, so read access is
# as broad as ScopeItem's own (whoever might build a Cost Sheet or just
# needs to see what a sport's accessories normally are).
CATALOG_READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
# Q.2 rule 6 precedent: "Master Settings screen is Director-only."
CATALOG_WRITE_ROLES = ("director",)


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

    catalog_items = (
        db.query(AccessoryCatalogItem)
        .filter(AccessoryCatalogItem.sport_id == sport.id, AccessoryCatalogItem.is_active.is_(True))
        .all()
    )
    if not catalog_items and not payload.custom_items:
        raise HTTPException(
            status_code=422,
            detail=f"No accessories catalog for {sport.name} -- specify custom_items",
        )

    missing_rates = [item.item_name for item in catalog_items if item.item_name not in payload.rates]
    if missing_rates:
        raise HTTPException(status_code=422, detail=f"Missing rate for: {', '.join(missing_rates)}")

    lines_to_create: list[CostSheetLine] = []
    applied = []
    for item in catalog_items:
        quantity = float(item.quantity_per_court) * project_sport.number_of_courts
        rate = payload.rates[item.item_name]
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                project_sport_id=payload.project_sport_id,
                work_package=WorkPackage.ACCESSORIES,
                category="Accessories",
                item_name=item.item_name,
                unit=item.unit,
                quantity=quantity,
                rate=rate,
                source=RateSource.MANUAL,
            )
        )
        applied.append({"item_name": item.item_name, "unit": item.unit, "quantity": quantity, "rate": rate})

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


# --------------------------------------------------------------------------
# Accessory catalog master (Part I / Module 9) -- Director-editable,
# replacing the former hardcoded ACCESSORY_CATALOG Python dict (the
# audit's "hardcoded technical catalogues" finding).
# --------------------------------------------------------------------------


class AccessoryCatalogItemOut(BaseModel):
    id: uuid.UUID
    sport_id: uuid.UUID
    item_name: str
    unit: str
    quantity_per_court: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@accessory_catalog_router.get("", response_model=list[AccessoryCatalogItemOut])
def list_accessory_catalog(
    sport_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_READ_ROLES)),
):
    query = db.query(AccessoryCatalogItem)
    if sport_id is not None:
        query = query.filter(AccessoryCatalogItem.sport_id == sport_id)
    if not include_inactive:
        query = query.filter(AccessoryCatalogItem.is_active.is_(True))
    return query.order_by(AccessoryCatalogItem.sport_id, AccessoryCatalogItem.item_name).all()


class AccessoryCatalogItemCreate(BaseModel):
    sport_id: uuid.UUID
    item_name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    quantity_per_court: float = Field(gt=0)


class AccessoryCatalogItemUpdate(BaseModel):
    item_name: str | None = None
    unit: str | None = None
    quantity_per_court: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


@accessory_catalog_router.post("", response_model=AccessoryCatalogItemOut, status_code=201)
def create_accessory_catalog_item(
    payload: AccessoryCatalogItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_WRITE_ROLES)),
):
    if not db.query(Sport).filter(Sport.id == payload.sport_id).first():
        raise HTTPException(status_code=404, detail="Sport not found")
    if (
        db.query(AccessoryCatalogItem)
        .filter(AccessoryCatalogItem.sport_id == payload.sport_id, AccessoryCatalogItem.item_name == payload.item_name)
        .first()
    ):
        raise HTTPException(status_code=409, detail=f"'{payload.item_name}' already exists for this sport")

    item = AccessoryCatalogItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@accessory_catalog_router.patch("/{item_id}", response_model=AccessoryCatalogItemOut)
def update_accessory_catalog_item(
    item_id: uuid.UUID,
    payload: AccessoryCatalogItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_WRITE_ROLES)),
):
    item = db.query(AccessoryCatalogItem).filter(AccessoryCatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Accessory catalog item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
