import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openpyxl import Workbook, load_workbook
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
from app.xlsx_utils import xlsx_header_row, xlsx_response

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


# --------------------------------------------------------------------------
# J.1 "Bulk actions (all AI / all Manual / category)" -- one filterable
# mark action (source flips AI<->Manual across many items at once, the
# multi-item version of POST .../confirm and its reverse) and one
# category-wide rate % change (the RATE_ITEM-table sibling of Q.2 rule 5's
# already-built Master Settings bulk_update_settings, since a "category" in
# J.1 means a group of rate items, not a group of settings).
# --------------------------------------------------------------------------


class BulkMarkRequest(BaseModel):
    source: RateSource
    category: str | None = None  # None = every rate item, regardless of category


class BulkMarkResult(BaseModel):
    updated_count: int
    updated_item_ids: list[uuid.UUID]


@rate_items_router.post("/bulk-mark", response_model=BulkMarkResult)
def bulk_mark_rate_items(
    payload: BulkMarkRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CONFIRM_ROLES)),
):
    """'All AI' / 'all Manual' (payload.category omitted) or a single
    category's items (payload.category set), flipped to payload.source in
    one action. Marking AI mirrors POST .../confirm (verified + today's
    confirmed_date); marking Manual is the reverse -- unverified, no
    confirmed_date, same as a freshly-created item."""
    query = db.query(RateItem).filter(RateItem.source != payload.source)
    if payload.category is not None:
        query = query.filter(RateItem.category == payload.category)
    items = query.all()

    for item in items:
        item.source = payload.source
        if payload.source == RateSource.AI:
            item.verified = True
            item.confirmed_date = datetime.now(UTC).date()
        else:
            item.verified = False
            item.confirmed_date = None
    db.commit()

    return BulkMarkResult(updated_count=len(items), updated_item_ids=[i.id for i in items])


class BulkRateUpdateRequest(BaseModel):
    category: str
    percent_change: float  # e.g. 6.0 for "steel +6%", -5.0 for "-5%"
    reason: str = Field(min_length=1)
    effective_from: date | None = None


class BulkRateUpdateResult(BaseModel):
    updated_count: int
    items: list[RateItemWithAlertOut]


@rate_items_router.post("/bulk-rate-update", response_model=BulkRateUpdateResult)
def bulk_update_rate_items(
    payload: BulkRateUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """J.1's category-wide '% change to a whole category' bulk action for
    the rate sheet -- same RATE_HISTORY-preserving mechanics as the
    single-item POST .../rate (close the open history row, open a new
    one), applied to every item in the category. Items already at zero
    rate are skipped (any % change of zero is still zero -- nothing to
    record). Each updated item's commodity alert is evaluated exactly as
    it is for a single-item change, so a bulk move that crosses the
    watch threshold surfaces the same warning it would one item at a
    time."""
    items = db.query(RateItem).filter(RateItem.category == payload.category).all()
    if not items:
        raise HTTPException(status_code=404, detail=f"No rate items found in category '{payload.category}'")

    effective_from = payload.effective_from or date.today()
    threshold = _commodity_alert_threshold_percent(db)
    results: list[RateItemWithAlertOut] = []

    for item in items:
        previous_rate = float(item.rate)
        if previous_rate == 0:
            continue
        new_rate = round(previous_rate * (1 + payload.percent_change / 100), 2)
        if new_rate == previous_rate:
            continue

        open_row = (
            db.query(RateHistory)
            .filter(RateHistory.rate_item_id == item.id, RateHistory.effective_to.is_(None))
            .order_by(RateHistory.effective_from.desc())
            .first()
        )
        if open_row is not None:
            closed_to = effective_from - timedelta(days=1)
            open_row.effective_to = closed_to if closed_to >= open_row.effective_from else open_row.effective_from

        item.rate = new_rate
        db.add(RateHistory(
            rate_item_id=item.id,
            rate=new_rate,
            effective_from=effective_from,
            effective_to=None,
            changed_by_id=current_user.id,
            reason=payload.reason,
        ))
        db.flush()

        alert = None
        if item.is_commodity_watched:
            percent_move = (new_rate - previous_rate) / previous_rate * 100
            if abs(percent_move) >= threshold:
                draft_rows, verified_rows = _affected_cost_sheets(db, item.id)
                alert = CommodityAlertOut(
                    triggered=True,
                    previous_rate=previous_rate,
                    new_rate=new_rate,
                    percent_move=round(percent_move, 2),
                    threshold_percent=threshold,
                    draft_cost_sheets=_to_affected_out(draft_rows),
                    verified_cost_sheets=_to_affected_out(verified_rows),
                )
        results.append(RateItemWithAlertOut(rate_item=_to_out(db, item), commodity_alert=alert))

    db.commit()
    return BulkRateUpdateResult(updated_count=len(results), items=results)


# --------------------------------------------------------------------------
# Excel export/import (P.2 Phase 1b: "Excel rate import" -- named alongside
# "rate verification workflow" in the same roadmap line, both J.1 features;
# distinct from Q.2 rule 6's Master Settings export/import, which covers
# global %/threshold config, not per-item rates. Appendix D item 1's "can
# be supplied as an Excel rate card" is this: NestaPrime's own existing
# rate-card spreadsheet, one row per material/item.)
# --------------------------------------------------------------------------

_RATE_ITEM_XLSX_COLUMNS = [
    "Category", "Item name", "Spec", "Unit", "HSN/SAC", "Rate", "Vendor", "City of quote",
    "Labour category key", "Commodity watched", "Source", "Verified",
]
_RATE_ITEM_IMPORT_DEFAULT_REASON = "Bulk Excel import"


@rate_items_router.get("/export")
def export_rate_items(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """One row per current rate item, in the same column order
    import_rate_items() expects back -- export-then-reimport unchanged is
    always a safe no-op (nothing differs, every row is skipped). Source
    and Verified are informational only here; import never sets them --
    J.1's governance ('PM or Director confirms -> becomes AI rate') stays
    the only path, so a bulk file can't quietly promote a rate to master."""
    labour_category_key_by_id = {lc.id: lc.key for lc in db.query(LabourCategory).all()}
    items = db.query(RateItem).order_by(RateItem.category, RateItem.item_name).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Rate Sheet"
    xlsx_header_row(ws, _RATE_ITEM_XLSX_COLUMNS)
    for item in items:
        ws.append(
            [
                item.category, item.item_name, item.spec, item.unit, item.hsn_sac, float(item.rate),
                item.vendor, item.city_of_quote, labour_category_key_by_id.get(item.labour_category_id),
                item.is_commodity_watched, item.source.value, item.verified,
            ]
        )
    return xlsx_response(wb, "rate-sheet.xlsx")


class RateItemImportRowError(BaseModel):
    row: int
    detail: str


class RateItemImportResult(BaseModel):
    created: list[RateItemOut]
    updated: list[RateItemOut]
    unchanged: int
    errors: list[RateItemImportRowError]


def _parse_import_bool(raw, default: bool = False) -> bool:
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "y")


@rate_items_router.post("/import", response_model=RateItemImportResult)
def import_rate_items(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Expects the same columns export_rate_items() produces, header row
    first. Matches an existing item by (category, item_name, spec) --
    NestaPrime's own natural key for "the same line" on a rate card.

    - No match: creates a new item (always MANUAL/unverified, per J.1 --
      Source/Verified columns are ignored on create, same as they're
      ignored on update below), plus its opening RateHistory row.
    - Match, rate differs: updates the rate through the same
      RateHistory-preserving mechanics as POST .../rate (close the open
      history row, open a new one) -- never a silent overwrite. Other
      changed fields (vendor, spec, unit, hsn_sac, city_of_quote, labour
      category, commodity-watched) are applied directly, same as PATCH
      .../{id}.
    - Match, rate identical: counted unchanged (even if some other field
      also changed -- see below) and skipped, so an unmodified
      export-then-reimport is always a safe no-op.

    Deliberately out of scope: a rate change made here does NOT evaluate
    the commodity alert (POST .../rate's draft/verified cost-sheet
    breakdown) -- a bulk file can touch far more items than a Director
    would want individually reviewed mid-import. Use the Rate Sheet
    screen afterwards to check any commodity-watched item's alert if
    needed; nothing about the alert itself is lost, only deferred.

    One bad row (missing category/item_name/unit/rate, an unreadable
    rate, an unknown labour category key) is recorded as a per-row error
    and does not stop the rest of the file from importing."""
    try:
        wb = load_workbook(file.file, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read this file as an Excel workbook: {exc}")
    ws = wb.active

    labour_category_id_by_key = {lc.key: lc.id for lc in db.query(LabourCategory).all()}
    existing_by_key = {
        (i.category, i.item_name, i.spec): i
        for i in db.query(RateItem).all()
    }

    created: list[RateItem] = []
    updated: list[RateItem] = []
    unchanged = 0
    errors: list[RateItemImportRowError] = []

    for row_number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row is None or all(cell in (None, "") for cell in row):
            continue  # blank row -- e.g. Excel's own trailing rows
        (
            category_cell, item_name_cell, spec_cell, unit_cell, hsn_sac_cell, rate_cell,
            vendor_cell, city_cell, labour_key_cell, watched_cell, _source_cell, _verified_cell,
        ) = (list(row) + [None] * (len(_RATE_ITEM_XLSX_COLUMNS) - len(row)))[: len(_RATE_ITEM_XLSX_COLUMNS)]

        try:
            category = str(category_cell).strip() if category_cell not in (None, "") else ""
            if not category:
                raise ValueError("Category is required")
            item_name = str(item_name_cell).strip() if item_name_cell not in (None, "") else ""
            if not item_name:
                raise ValueError("Item name is required")
            spec = str(spec_cell).strip() if spec_cell not in (None, "") else None
            unit = str(unit_cell).strip() if unit_cell not in (None, "") else ""
            if not unit:
                raise ValueError("Unit is required")
            hsn_sac = str(hsn_sac_cell).strip() if hsn_sac_cell not in (None, "") else ""
            if rate_cell in (None, ""):
                raise ValueError("Rate is required")
            rate = float(rate_cell)
            vendor = str(vendor_cell).strip() if vendor_cell not in (None, "") else None
            city_of_quote = str(city_cell).strip() if city_cell not in (None, "") else None
            labour_category_id = None
            if labour_key_cell not in (None, ""):
                labour_key = str(labour_key_cell).strip()
                if labour_key not in labour_category_id_by_key:
                    raise ValueError(f"Unknown labour category key '{labour_key}'")
                labour_category_id = labour_category_id_by_key[labour_key]
            is_commodity_watched = _parse_import_bool(watched_cell)
        except (ValueError, TypeError) as exc:
            errors.append(RateItemImportRowError(row=row_number, detail=str(exc)))
            continue

        existing = existing_by_key.get((category, item_name, spec))
        if existing is None:
            item = RateItem(
                source=RateSource.MANUAL,
                verified=False,
                category=category, item_name=item_name, spec=spec, unit=unit, hsn_sac=hsn_sac, rate=rate,
                vendor=vendor, city_of_quote=city_of_quote, labour_category_id=labour_category_id,
                is_commodity_watched=is_commodity_watched,
            )
            db.add(item)
            db.flush()
            db.add(RateHistory(
                rate_item_id=item.id, rate=rate, effective_from=date.today(), effective_to=None,
                changed_by_id=current_user.id, reason=_RATE_ITEM_IMPORT_DEFAULT_REASON,
            ))
            existing_by_key[(category, item_name, spec)] = item
            created.append(item)
            continue

        previous_rate = float(existing.rate)
        if rate != previous_rate:
            open_row = (
                db.query(RateHistory)
                .filter(RateHistory.rate_item_id == existing.id, RateHistory.effective_to.is_(None))
                .order_by(RateHistory.effective_from.desc())
                .first()
            )
            if open_row is not None:
                open_row.effective_to = date.today()
            existing.rate = rate
            db.add(RateHistory(
                rate_item_id=existing.id, rate=rate, effective_from=date.today(), effective_to=None,
                changed_by_id=current_user.id, reason=_RATE_ITEM_IMPORT_DEFAULT_REASON,
            ))
            existing.unit = unit
            existing.hsn_sac = hsn_sac
            existing.vendor = vendor
            existing.city_of_quote = city_of_quote
            existing.labour_category_id = labour_category_id
            existing.is_commodity_watched = is_commodity_watched
            updated.append(existing)
        else:
            unchanged += 1

    db.commit()
    for item in created + updated:
        db.refresh(item)
    return RateItemImportResult(
        created=[_to_out(db, i) for i in created],
        updated=[_to_out(db, i) for i in updated],
        unchanged=unchanged,
        errors=errors,
    )
