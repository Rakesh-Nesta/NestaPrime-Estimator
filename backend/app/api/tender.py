import math
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value, get_gst_rate_percent
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import Quotation
from app.models.project import Project
from app.models.technical_bid_checklist import TechnicalBidChecklistItem, TechnicalBidChecklistKey
from app.models.tender_details import TenderCompetitorBid, TenderDetails

tender_details_router = APIRouter(prefix="/projects", tags=["tender-details"])
tender_calc_router = APIRouter(prefix="/tender", tags=["tender-calculators"])
l1_view_router = APIRouter(tags=["tender-l1-view"])

# Tender Mode is money-adjacent (EMD, retention, BG %) the same way K's
# commercial layer is -- every K.1 step touching it is "PM, Director" only,
# never Sales, so this module follows the same restriction (K.3).
ROLES = ("pm", "director")


class TenderDetailsCreate(BaseModel):
    emd_amount: float | None = None
    emd_validity_date: date | None = None
    retention_percent: float = Field(gt=0)
    performance_bg_percent: float = Field(gt=0)
    dlp_months: int = Field(default=12, gt=0)
    bid_due_date: date | None = None
    pre_bid_meeting_date: date | None = None
    opening_date: date | None = None


class TenderDetailsOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    emd_amount: float | None
    emd_validity_date: date | None
    retention_percent: float
    performance_bg_percent: float
    dlp_months: int
    bid_due_date: date | None
    pre_bid_meeting_date: date | None
    opening_date: date | None
    # Derived, M.3/Part L reminders -- computed at read time (no
    # scheduler exists in this app to fire an actual reminder message;
    # see documents.py's own note on the same limitation). True inside
    # the lookahead window up to and including the date itself.
    pre_bid_meeting_reminder_due: bool = False
    bid_due_reminder_due: bool = False
    # True once EMD validity has lapsed -- the deposit should have been
    # claimed back by then.
    emd_refund_reminder_due: bool = False

    model_config = ConfigDict(from_attributes=True)


TENDER_REMINDER_LOOKAHEAD_DAYS_DEFAULT = 2


def _tender_reminder_lookahead_days(db: Session) -> int:
    value = get_current_setting_value(db, "tender_reminder_lookahead_days")
    return int(value) if value is not None else TENDER_REMINDER_LOOKAHEAD_DAYS_DEFAULT


def _tender_details_to_out(db: Session, row: TenderDetails) -> TenderDetailsOut:
    out = TenderDetailsOut.model_validate(row)
    today = datetime.now(UTC).date()
    lookahead = timedelta(days=_tender_reminder_lookahead_days(db))
    if row.pre_bid_meeting_date is not None:
        out.pre_bid_meeting_reminder_due = today <= row.pre_bid_meeting_date <= today + lookahead
    if row.bid_due_date is not None:
        out.bid_due_reminder_due = today <= row.bid_due_date <= today + lookahead
    if row.emd_validity_date is not None:
        out.emd_refund_reminder_due = today > row.emd_validity_date
    return out


@tender_details_router.post(
    "/{project_id}/tender-details", response_model=TenderDetailsOut, status_code=201
)
def create_tender_details(
    project_id: uuid.UUID,
    payload: TenderDetailsCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.tender_mode:
        raise HTTPException(
            status_code=400,
            detail="Tender details only apply to Tender Mode (Government client) projects (Part L)",
        )

    existing = db.query(TenderDetails).filter(TenderDetails.project_id == project_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tender details already exist for this project")

    row = TenderDetails(project_id=project_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _tender_details_to_out(db, row)


@tender_details_router.get("/{project_id}/tender-details", response_model=TenderDetailsOut)
def get_tender_details(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    row = db.query(TenderDetails).filter(TenderDetails.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tender details not found for this project")
    return _tender_details_to_out(db, row)


def _get_tender_details_or_404(db: Session, project_id: uuid.UUID) -> TenderDetails:
    row = db.query(TenderDetails).filter(TenderDetails.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tender details not found for this project")
    return row


class TenderCompetitorBidCreate(BaseModel):
    bidder_name: str = Field(min_length=1)
    amount: float = Field(gt=0)


class TenderCompetitorBidOut(BaseModel):
    id: uuid.UUID
    tender_details_id: uuid.UUID
    bidder_name: str
    amount: float
    recorded_by_id: uuid.UUID
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


@tender_details_router.post(
    "/{project_id}/tender-details/competitor-bids", response_model=TenderCompetitorBidOut, status_code=201
)
def add_competitor_bid(
    project_id: uuid.UUID,
    payload: TenderCompetitorBidCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """Part L 'Price basis' row: 'L1 mode shows margin at proposed price
    live.' The blueprint gives no schema for competing bids -- each
    recorded amount (a pre-bid estimate, a rumoured figure, an
    opening-day reading) feeds the live L1 comparison below as PM/
    Director learn of it during price discovery."""
    tender_details = _get_tender_details_or_404(db, project_id)
    bid = TenderCompetitorBid(
        tender_details_id=tender_details.id,
        bidder_name=payload.bidder_name,
        amount=payload.amount,
        recorded_by_id=current_user.id,
    )
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return bid


@tender_details_router.get(
    "/{project_id}/tender-details/competitor-bids", response_model=list[TenderCompetitorBidOut]
)
def list_competitor_bids(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    tender_details = _get_tender_details_or_404(db, project_id)
    return (
        db.query(TenderCompetitorBid)
        .filter(TenderCompetitorBid.tender_details_id == tender_details.id)
        .order_by(TenderCompetitorBid.amount)
        .all()
    )


@tender_details_router.delete(
    "/{project_id}/tender-details/competitor-bids/{bid_id}", status_code=204
)
def delete_competitor_bid(
    project_id: uuid.UUID,
    bid_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    tender_details = _get_tender_details_or_404(db, project_id)
    bid = (
        db.query(TenderCompetitorBid)
        .filter(TenderCompetitorBid.id == bid_id, TenderCompetitorBid.tender_details_id == tender_details.id)
        .first()
    )
    if not bid:
        raise HTTPException(status_code=404, detail="Competitor bid not found")
    db.delete(bid)
    db.commit()


class L1ViewOut(BaseModel):
    quotation_id: uuid.UUID
    our_price: float
    margin_percent: float | None  # stripped for Sales (K.3), same as QuotationOut
    competitor_bids: list[TenderCompetitorBidOut]
    lowest_competitor_amount: float | None
    # None = no competitor bids on file yet, so there's nothing to rank
    # against -- distinct from False (we're beaten by at least one bid).
    is_l1: bool | None
    rank: int | None


@l1_view_router.get("/quotations/{quotation_id}/l1-view", response_model=L1ViewOut)
def get_l1_view(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    """Part L 'Price basis' row: 'L1 mode shows margin at proposed price
    live.' Recomputed on every call from the Quotation's current
    quotation_total and whatever competitor bids are on file -- 'live'
    in the sense that it always reflects the latest of either, not a
    snapshot taken once at tender entry. our_price is the GST-basis
    figure a tender is actually compared on (quotation_total already
    carries whichever gst_mode this Quotation used)."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    project = db.query(Project).filter(Project.id == quotation.project_id).first()
    if not project or not project.tender_mode:
        raise HTTPException(
            status_code=400, detail="The L1 view only applies to Tender Mode (Government client) projects (Part L)"
        )
    tender_details = _get_tender_details_or_404(db, project.id)

    bids = (
        db.query(TenderCompetitorBid)
        .filter(TenderCompetitorBid.tender_details_id == tender_details.id)
        .order_by(TenderCompetitorBid.amount)
        .all()
    )
    our_price = float(quotation.quotation_total)
    lowest_competitor_amount = float(bids[0].amount) if bids else None
    is_l1 = our_price <= lowest_competitor_amount if lowest_competitor_amount is not None else None
    rank = 1 + sum(1 for b in bids if float(b.amount) < our_price) if bids else None

    margin_percent = None if current_user.role.value == "sales" else float(quotation.margin_percent)

    return L1ViewOut(
        quotation_id=quotation.id,
        our_price=our_price,
        margin_percent=margin_percent,
        competitor_bids=bids,
        lowest_competitor_amount=lowest_competitor_amount,
        is_l1=is_l1,
        rank=rank,
    )


class TechnicalBidChecklistItemOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: TechnicalBidChecklistKey
    confirmed: bool
    confirmed_at: datetime | None
    confirmed_by_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


def _get_or_seed_checklist(db: Session, project_id: uuid.UUID) -> list[TechnicalBidChecklistItem]:
    """Part L 'Documents' row: 'Technical bid checklist (GST, PAN,
    turnover, past work certificates, ISO).' Five fixed items, lazily
    created the first time this project's checklist is read -- the
    blueprint describes no separate creation step, so a plain project-
    scoped GET is the least-invented place to seed them."""
    existing = {
        item.key: item
        for item in db.query(TechnicalBidChecklistItem).filter(TechnicalBidChecklistItem.project_id == project_id).all()
    }
    for key in TechnicalBidChecklistKey:
        if key not in existing:
            item = TechnicalBidChecklistItem(project_id=project_id, key=key)
            db.add(item)
            existing[key] = item
    db.commit()
    return [existing[key] for key in TechnicalBidChecklistKey]


@tender_details_router.get(
    "/{project_id}/technical-bid-checklist", response_model=list[TechnicalBidChecklistItemOut]
)
def get_technical_bid_checklist(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.tender_mode:
        raise HTTPException(
            status_code=400,
            detail="The technical bid checklist only applies to Tender Mode (Government client) projects (Part L)",
        )
    return _get_or_seed_checklist(db, project_id)


class TechnicalBidChecklistItemUpdate(BaseModel):
    confirmed: bool


@tender_details_router.patch(
    "/{project_id}/technical-bid-checklist/{key}", response_model=TechnicalBidChecklistItemOut
)
def update_technical_bid_checklist_item(
    project_id: uuid.UUID,
    key: TechnicalBidChecklistKey,
    payload: TechnicalBidChecklistItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.tender_mode:
        raise HTTPException(
            status_code=400,
            detail="The technical bid checklist only applies to Tender Mode (Government client) projects (Part L)",
        )
    _get_or_seed_checklist(db, project_id)

    item = (
        db.query(TechnicalBidChecklistItem)
        .filter(TechnicalBidChecklistItem.project_id == project_id, TechnicalBidChecklistItem.key == key)
        .first()
    )
    item.confirmed = payload.confirmed
    item.confirmed_at = datetime.now(UTC) if payload.confirmed else None
    item.confirmed_by_id = current_user.id if payload.confirmed else None
    db.commit()
    db.refresh(item)
    return item


def compute_bg_cost(
    bg_amount: float, bank_charge_percent_pa: float, contract_weeks: float, dlp_months: int
) -> tuple[int, float]:
    """L: 'BG cost = BG amount x bank charge [1-2% p.a.] x (contract months
    + DLP months) / 12 where contract months = ceil(schedule weeks / 4.33)
    ... never shown as a separate line to the client.' Shared by the
    standalone /tender/performance-bg-cost calculator below and the real
    K.1 step 4A cost-sheet line (POST /cost-sheets/{id}/tender-overheads
    in overheads.py) so both use the exact same formula."""
    contract_months = math.ceil(contract_weeks / 4.33)
    bg_cost = bg_amount * (bank_charge_percent_pa / 100) * (contract_months + dlp_months) / 12
    return contract_months, bg_cost


class PerformanceBgCostRequest(BaseModel):
    bg_amount: float = Field(gt=0)
    bank_charge_percent_pa: float = Field(gt=0)
    contract_weeks: float = Field(gt=0)
    dlp_months: int = Field(gt=0)


class PerformanceBgCostOut(BaseModel):
    contract_months: int
    bg_cost: float


@tender_calc_router.post("/performance-bg-cost", response_model=PerformanceBgCostOut)
def performance_bg_cost(
    payload: PerformanceBgCostRequest,
    current_user=Depends(require_roles(*ROLES)),
):
    """Standalone calculator for the same formula K.1 step 4A now applies
    for real via POST /cost-sheets/{id}/tender-overheads -- kept for
    PM/Director to sanity-check a figure before committing it as a line,
    same pattern as the Part K pricing calculator alongside the real
    pricing engine."""
    contract_months, bg_cost = compute_bg_cost(
        payload.bg_amount, payload.bank_charge_percent_pa, payload.contract_weeks, payload.dlp_months
    )
    return PerformanceBgCostOut(contract_months=contract_months, bg_cost=bg_cost)


class NetReceivableRequest(BaseModel):
    quotation_total: float = Field(gt=0)
    retention_percent: float = Field(gt=0)
    # Part L "Statutory": "GST-TDS 2% by government/PSU payer." The
    # blueprint's own normative K.1b section (v5.1.9) explicitly retired
    # GST-TDS logic ("TDS deduction by the client ... happens outside
    # this app") -- built anyway per an explicit, informed decision to
    # override that retirement note. Modelled as a receipt-side deduction
    # the government/PSU payer withholds (like real GST TDS under CGST
    # Act Section 51: 2% of the taxable/ex-GST value, not the GST-
    # inclusive total), for NestaPrime's own net-cash-received visibility
    # only -- never computed, shown, or gated on anywhere in the client-
    # facing Quotation/BOQ PDF.
    gst_tds_percent: float | None = Field(default=None, ge=0)


class NetReceivableOut(BaseModel):
    retention_amount: float
    gst_tds_amount: float
    net_receivable: float


@tender_calc_router.post("/net-receivable", response_model=NetReceivableOut)
def net_receivable(
    payload: NetReceivableRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """L: 'Security deposit / retention: 5-10% [confirm] withheld -> shown
    in net receivable.' Composable with Part K's /pricing/quote output
    (quotation_total). GST-TDS (optional; see NetReceivableRequest) is
    computed on the ex-GST value -- quotation_total already carries K.1's
    flat 18% (K.1b), so ex_gst = quotation_total / (1 + gst_rate/100) --
    and deducted alongside retention."""
    retention_amount = payload.quotation_total * payload.retention_percent / 100

    gst_tds_amount = 0.0
    if payload.gst_tds_percent:
        gst_rate_percent = get_gst_rate_percent(db)
        ex_gst_value = payload.quotation_total / (1 + gst_rate_percent / 100)
        gst_tds_amount = ex_gst_value * payload.gst_tds_percent / 100

    return NetReceivableOut(
        retention_amount=retention_amount,
        gst_tds_amount=gst_tds_amount,
        net_receivable=payload.quotation_total - retention_amount - gst_tds_amount,
    )
