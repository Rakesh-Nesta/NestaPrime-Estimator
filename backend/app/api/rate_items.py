import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine, CostSheetStatus
from app.models.project import Project
from app.models.rate_history import RateHistory
from app.models.rate_item import LabourCategory, RateItem, RateSource
from app.models.vendor import Vendor

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
# Q.1: "commodity alert threshold" -- Director-configurable, default +-10%.
COMMODITY_ALERT_THRESHOLD_PERCENT_DEFAULT = 10.0


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
    is_commodity_watched: bool = False
    # RATE_HISTORY context for this item's first rate row -- all optional.
    vendor_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    reason: str | None = None


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
    is_commodity_watched: bool
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


def _validate_vendor_and_project(db: Session, vendor_id: uuid.UUID | None, project_id: uuid.UUID | None) -> None:
    if vendor_id is not None and not db.query(Vendor).filter(Vendor.id == vendor_id).first():
        raise HTTPException(status_code=404, detail="Vendor not found")
    if project_id is not None and not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")


@rate_items_router.get("", response_model=list[RateItemOut])
def list_rate_items(
    watched_only: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(RateItem)
    if watched_only:
        query = query.filter(RateItem.is_commodity_watched.is_(True))
    items = query.order_by(RateItem.category, RateItem.item_name).all()
    return [_to_out(db, i) for i in items]


@rate_items_router.post("", response_model=RateItemOut, status_code=201)
def create_rate_item(
    payload: RateItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """J.1: every new entry starts as a Manual, unverified rate. It only
    becomes an AI (master) rate via POST /rate-items/{id}/confirm.
    Part O RATE_HISTORY: this first rate is itself logged as the item's
    opening history row."""
    if payload.labour_category_id is not None:
        labour_category = (
            db.query(LabourCategory)
            .filter(LabourCategory.id == payload.labour_category_id)
            .first()
        )
        if not labour_category:
            raise HTTPException(status_code=404, detail="Labour category not found")
    _validate_vendor_and_project(db, payload.vendor_id, payload.project_id)

    item = RateItem(
        source=RateSource.MANUAL,
        verified=False,
        category=payload.category,
        item_name=payload.item_name,
        spec=payload.spec,
        unit=payload.unit,
        hsn_sac=payload.hsn_sac,
        rate=payload.rate,
        vendor=payload.vendor,
        city_of_quote=payload.city_of_quote,
        labour_category_id=payload.labour_category_id,
        is_commodity_watched=payload.is_commodity_watched,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    db.add(RateHistory(
        rate_item_id=item.id,
        rate=payload.rate,
        effective_from=date.today(),
        effective_to=None,
        vendor_id=payload.vendor_id,
        project_id=payload.project_id,
        changed_by_id=current_user.id,
        reason=payload.reason or "Initial rate",
    ))
    db.commit()
    return _to_out(db, item)


class RateItemUpdate(BaseModel):
    """rate is deliberately excluded -- every rate VALUE change must go
    through POST /rate-items/{id}/rate so it's captured in RATE_HISTORY;
    a silent bypass here would defeat Part O's "one row per change"
    guarantee."""

    category: str | None = None
    item_name: str | None = None
    spec: str | None = None
    unit: str | None = None
    hsn_sac: str | None = None
    vendor: str | None = None
    city_of_quote: str | None = None
    labour_category_id: uuid.UUID | None = None
    is_commodity_watched: bool | None = None


@rate_items_router.patch("/{rate_item_id}", response_model=RateItemOut)
def update_rate_item(
    rate_item_id: uuid.UUID,
    payload: RateItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    item = db.query(RateItem).filter(RateItem.id == rate_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Rate item not found")
    if payload.labour_category_id is not None:
        if not db.query(LabourCategory).filter(LabourCategory.id == payload.labour_category_id).first():
            raise HTTPException(status_code=404, detail="Labour category not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
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


# ---------------------------------------------------------------------------
# Part O RATE_HISTORY + Part I / Q.1 commodity alert
# ---------------------------------------------------------------------------


class RateHistoryOut(BaseModel):
    id: uuid.UUID
    rate_item_id: uuid.UUID
    rate: float
    effective_from: date
    effective_to: date | None
    vendor_id: uuid.UUID | None
    project_id: uuid.UUID | None
    changed_by_id: uuid.UUID
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@rate_items_router.get("/{rate_item_id}/history", response_model=list[RateHistoryOut])
def get_rate_history(
    rate_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    if not db.query(RateItem).filter(RateItem.id == rate_item_id).first():
        raise HTTPException(status_code=404, detail="Rate item not found")
    return (
        db.query(RateHistory)
        .filter(RateHistory.rate_item_id == rate_item_id)
        .order_by(RateHistory.effective_from.desc(), RateHistory.created_at.desc())
        .all()
    )


class RateUpdateRequest(BaseModel):
    rate: float = Field(gt=0)
    reason: str = Field(min_length=1)
    vendor_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    effective_from: date | None = None


class AffectedCostSheetOut(BaseModel):
    cost_sheet_id: uuid.UUID
    document_no: str
    project_id: uuid.UUID
    status: CostSheetStatus


class CommodityAlertOut(BaseModel):
    triggered: bool
    previous_rate: float
    new_rate: float
    percent_move: float
    threshold_percent: float
    # Eligible for the actual bulk-sync action (POST .../sync-draft-lines).
    draft_cost_sheets: list[AffectedCostSheetOut]
    # Informational only -- a verified cost sheet's figures are frozen
    # (M.2 rule 5) and are never touched by a later rate change.
    verified_cost_sheets: list[AffectedCostSheetOut]


class RateItemWithAlertOut(BaseModel):
    rate_item: RateItemOut
    commodity_alert: CommodityAlertOut | None


def _commodity_alert_threshold_percent(db: Session) -> float:
    value = get_current_setting_value(db, "commodity_alert_threshold_percent")
    return float(value) if value is not None else COMMODITY_ALERT_THRESHOLD_PERCENT_DEFAULT


def _affected_cost_sheets(db: Session, rate_item_id: uuid.UUID) -> tuple[list[CostSheet], list[CostSheet]]:
    rows = (
        db.query(CostSheet)
        .join(CostSheetLine, CostSheetLine.cost_sheet_id == CostSheet.id)
        .filter(CostSheetLine.rate_item_id == rate_item_id, CostSheet.status != CostSheetStatus.SUPERSEDED)
        .distinct()
        .all()
    )
    draft = [r for r in rows if r.status == CostSheetStatus.DRAFT]
    verified = [r for r in rows if r.status == CostSheetStatus.VERIFIED]
    return draft, verified


def _to_affected_out(rows: list[CostSheet]) -> list[AffectedCostSheetOut]:
    return [
        AffectedCostSheetOut(cost_sheet_id=r.id, document_no=r.document_no, project_id=r.project_id, status=r.status)
        for r in rows
    ]


@rate_items_router.post("/{rate_item_id}/rate", response_model=RateItemWithAlertOut)
def update_rate_value(
    rate_item_id: uuid.UUID,
    payload: RateUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Part O RATE_HISTORY: the only path that changes a rate item's rate
    value -- every call closes the previously-open history row and opens
    a new one. When the item is commodity-watched and the move against
    its previous (master) rate is >= Q.1's commodity alert threshold, the
    response's commodity_alert flags every open Cost Sheet using it and
    identifies which are actually eligible for a bulk sync (draft) versus
    frozen and informational only (verified, M.2 rule 5)."""
    item = db.query(RateItem).filter(RateItem.id == rate_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Rate item not found")
    _validate_vendor_and_project(db, payload.vendor_id, payload.project_id)

    previous_rate = float(item.rate)
    if payload.rate == previous_rate:
        raise HTTPException(status_code=422, detail="New rate matches the current rate -- nothing to change")

    effective_from = payload.effective_from or date.today()

    open_row = (
        db.query(RateHistory)
        .filter(RateHistory.rate_item_id == item.id, RateHistory.effective_to.is_(None))
        .order_by(RateHistory.effective_from.desc())
        .first()
    )
    if open_row is not None:
        closed_to = effective_from - timedelta(days=1)
        open_row.effective_to = closed_to if closed_to >= open_row.effective_from else open_row.effective_from

    item.rate = payload.rate
    db.add(RateHistory(
        rate_item_id=item.id,
        rate=payload.rate,
        effective_from=effective_from,
        effective_to=None,
        vendor_id=payload.vendor_id,
        project_id=payload.project_id,
        changed_by_id=current_user.id,
        reason=payload.reason,
    ))
    db.commit()
    db.refresh(item)

    alert = None
    if item.is_commodity_watched and previous_rate > 0:
        percent_move = (payload.rate - previous_rate) / previous_rate * 100
        threshold = _commodity_alert_threshold_percent(db)
        if abs(percent_move) >= threshold:
            draft_rows, verified_rows = _affected_cost_sheets(db, item.id)
            alert = CommodityAlertOut(
                triggered=True,
                previous_rate=previous_rate,
                new_rate=payload.rate,
                percent_move=round(percent_move, 2),
                threshold_percent=threshold,
                draft_cost_sheets=_to_affected_out(draft_rows),
                verified_cost_sheets=_to_affected_out(verified_rows),
            )

    return RateItemWithAlertOut(rate_item=_to_out(db, item), commodity_alert=alert)


class BulkSyncResult(BaseModel):
    updated_line_count: int
    updated_cost_sheet_ids: list[uuid.UUID]


@rate_items_router.post("/{rate_item_id}/sync-draft-lines", response_model=BulkSyncResult)
def sync_draft_lines_to_master_rate(
    rate_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CONFIRM_ROLES)),
):
    """The commodity alert's 'suggests a bulk update' (Q.2 rule 5's
    precedent), applied to CostSheetLines rather than Settings: sets
    every line referencing this rate item to its current master rate --
    but ONLY on draft cost sheets. A verified cost sheet's figures are
    frozen by M.2 rule 5 and must never drift when the master rate sheet
    changes later (see CostSheetLine's own docstring); its lines are
    silently skipped here rather than treated as an error."""
    item = db.query(RateItem).filter(RateItem.id == rate_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Rate item not found")

    lines = (
        db.query(CostSheetLine)
        .join(CostSheet, CostSheet.id == CostSheetLine.cost_sheet_id)
        .filter(CostSheetLine.rate_item_id == rate_item_id, CostSheet.status == CostSheetStatus.DRAFT)
        .all()
    )
    updated_cost_sheet_ids: set[uuid.UUID] = set()
    for line in lines:
        line.rate = item.rate
        updated_cost_sheet_ids.add(line.cost_sheet_id)
    db.commit()

    return BulkSyncResult(updated_line_count=len(lines), updated_cost_sheet_ids=list(updated_cost_sheet_ids))
