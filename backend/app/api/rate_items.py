import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.rate_item import LabourCategory, RateItem, RateSource

labour_categories_router = APIRouter(prefix="/labour-categories", tags=["labour-categories"])
rate_items_router = APIRouter(prefix="/rate-items", tags=["rate-items"])

# Rates are cost-side, internal-only data (J.4: Cost Sheet / Material
# Consumption exports are explicitly "internal only") — Sales never sees
# this, matching K.3's principle that margin-relevant data is enforced at
# the API, not just hidden in the browser.
READ_ROLES = ("pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("pm", "director", "procurement")
CONFIRM_ROLES = ("pm", "director")

# Fallback when Part Q's Master Settings has no row yet (e.g. a fresh test DB).
STALE_AFTER_DAYS_DEFAULT = 90


class LabourCategoryOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    default_percent: float

    model_config = ConfigDict(from_attributes=True)


@labour_categories_router.get("", response_model=list[LabourCategoryOut])
def list_labour_categories(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return db.query(LabourCategory).order_by(LabourCategory.name).all()


class RateItemCreate(BaseModel):
    category: str
    item_name: str
    spec: str | None = None
    unit: str
    hsn_sac: str
    rate: float
    vendor: str | None = None
    city_of_quote: str | None = None
    labour_category_id: uuid.UUID | None = None


class RateItemOut(BaseModel):
    id: uuid.UUID
    category: str
    item_name: str
    spec: str | None
    unit: str
    hsn_sac: str
    rate: float
    source: RateSource
    verified: bool
    vendor: str | None
    confirmed_date: date | None
    city_of_quote: str | None
    labour_category_id: uuid.UUID | None
    is_stale: bool = False  # derived; _to_out() sets the real value

    model_config = ConfigDict(from_attributes=True)


def _to_out(db: Session, item: RateItem) -> RateItemOut:
    stale_after_days_str = get_current_setting_value(db, "rate_stale_after_days")
    stale_after_days = int(stale_after_days_str) if stale_after_days_str is not None else STALE_AFTER_DAYS_DEFAULT

    out = RateItemOut.model_validate(item)
    out.is_stale = (
        item.source == RateSource.AI
        and item.confirmed_date is not None
        and (datetime.now(UTC).date() - item.confirmed_date).days > stale_after_days
    )
    return out


@rate_items_router.get("", response_model=list[RateItemOut])
def list_rate_items(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    items = db.query(RateItem).order_by(RateItem.category, RateItem.item_name).all()
    return [_to_out(db, i) for i in items]


@rate_items_router.post("", response_model=RateItemOut, status_code=201)
def create_rate_item(
    payload: RateItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """J.1: every new entry starts as a Manual, unverified rate. It only
    becomes an AI (master) rate via POST /rate-items/{id}/confirm."""
    if payload.labour_category_id is not None:
        labour_category = (
            db.query(LabourCategory)
            .filter(LabourCategory.id == payload.labour_category_id)
            .first()
        )
        if not labour_category:
            raise HTTPException(status_code=404, detail="Labour category not found")

    item = RateItem(source=RateSource.MANUAL, verified=False, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(db, item)


@rate_items_router.post("/{rate_item_id}/confirm", response_model=RateItemOut)
def confirm_rate_item(
    rate_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CONFIRM_ROLES)),
):
    """J.1: 'PM or Director confirms -> becomes AI rate.'"""
    item = db.query(RateItem).filter(RateItem.id == rate_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Rate item not found")

    if item.source == RateSource.AI:
        raise HTTPException(status_code=400, detail="Rate item is already an AI (confirmed) rate")

    item.source = RateSource.AI
    item.verified = True
    item.confirmed_date = datetime.now(UTC).date()
    db.commit()
    db.refresh(item)
    return _to_out(db, item)
