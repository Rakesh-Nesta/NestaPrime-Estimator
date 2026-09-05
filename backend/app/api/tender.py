import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import Project
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
    """L: 'BG cost = BG amount x bank charge [1-2% p.a.] x (contract months
    + DLP months) / 12 where contract months = ceil(schedule weeks / 4.33)
    ... never shown as a separate line to the client' -- it feeds K.1 step
    4A once a real cost buildup exists to add it into; here it's a
    standalone calculator, same pattern as the Part K pricing calculator."""
    contract_months = math.ceil(payload.contract_weeks / 4.33)
    bg_cost = (
        payload.bg_amount
        * (payload.bank_charge_percent_pa / 100)
        * (contract_months + payload.dlp_months)
        / 12
    )
    return PerformanceBgCostOut(contract_months=contract_months, bg_cost=bg_cost)


class NetReceivableRequest(BaseModel):
    quotation_total: float = Field(gt=0)
    retention_percent: float = Field(gt=0)


class NetReceivableOut(BaseModel):
    retention_amount: float
    net_receivable: float


@tender_calc_router.post("/net-receivable", response_model=NetReceivableOut)
def net_receivable(
    payload: NetReceivableRequest,
    current_user=Depends(require_roles(*ROLES)),
):
    """L: 'Security deposit / retention: 5-10% [confirm] withheld -> shown
    in net receivable.' Composable with Part K's /pricing/quote output
    (quotation_total)."""
    retention_amount = payload.quotation_total * payload.retention_percent / 100
    return NetReceivableOut(
        retention_amount=retention_amount,
        net_receivable=payload.quotation_total - retention_amount,
    )
