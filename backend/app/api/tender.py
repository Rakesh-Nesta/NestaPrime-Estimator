import math
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.settings import get_gst_rate_percent
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import Project
from app.models.technical_bid_checklist import TechnicalBidChecklistItem, TechnicalBidChecklistKey
from app.models.tender_details import TenderDetails

tender_details_router = APIRouter(prefix="/projects", tags=["tender-details"])
tender_calc_router = APIRouter(prefix="/tender", tags=["tender-calculators"])

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

    model_config = ConfigDict(from_attributes=True)


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
    return row


@tender_details_router.get("/{project_id}/tender-details", response_model=TenderDetailsOut)
def get_tender_details(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    row = db.query(TenderDetails).filter(TenderDetails.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tender details not found for this project")
    return row


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
