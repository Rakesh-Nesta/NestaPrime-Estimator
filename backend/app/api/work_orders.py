import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import Quotation, QuotationStatus
from app.models.work_order import WorkOrder, WorkOrderPaymentEntry, WorkOrderStatus

work_orders_router = APIRouter(tags=["work-orders"])

# M.1 stage 4 ("Work Order & Actuals") lists only PM/Director in its role
# column -- unlike the Estimate/Quotation stages, Sales has no role here.
ROLES = ("pm", "director")

_LEGAL_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.AWARDED: {WorkOrderStatus.IN_PROGRESS},
    WorkOrderStatus.IN_PROGRESS: {WorkOrderStatus.COMPLETED},
    WorkOrderStatus.COMPLETED: set(),
}


class WorkOrderOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    quotation_id: uuid.UUID
    awarded_at: datetime
    status: WorkOrderStatus
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@work_orders_router.post(
    "/quotations/{quotation_id}/work-order", response_model=WorkOrderOut, status_code=201
)
def create_work_order(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """M.1 diagram: 'QUOTATION -> WORK ORDER / ACTUALS.' Stage 4's own
    status lifecycle starts at Awarded (M.1: 'Awarded -> In progress ->
    Completed')."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.WON:
        raise HTTPException(status_code=400, detail="A Work Order can only be created once the Quotation is Won")

    existing = db.query(WorkOrder).filter(WorkOrder.quotation_id == quotation_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="A Work Order already exists for this Quotation")

    work_order = WorkOrder(
        project_id=quotation.project_id,
        quotation_id=quotation_id,
        created_by_id=current_user.id,
    )
    db.add(work_order)
    db.commit()
    db.refresh(work_order)
    return work_order


@work_orders_router.get("/quotations/{quotation_id}/work-order", response_model=WorkOrderOut)
def get_work_order_for_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    work_order = db.query(WorkOrder).filter(WorkOrder.quotation_id == quotation_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="No Work Order for this Quotation")
    return work_order


class WorkOrderStatusUpdate(BaseModel):
    status: WorkOrderStatus


@work_orders_router.patch("/work-orders/{work_order_id}", response_model=WorkOrderOut)
def update_work_order_status(
    work_order_id: uuid.UUID,
    payload: WorkOrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """M.1: 'Awarded -> In progress -> Completed' -- a strict forward-only
    sequence, same convention as every other document status machine in
    this app (no skipping stages, no going backward)."""
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work Order not found")

    if payload.status not in _LEGAL_TRANSITIONS[work_order.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move a Work Order from {work_order.status.value} to {payload.status.value}",
        )
    work_order.status = payload.status
    db.commit()
    db.refresh(work_order)
    return work_order


class WorkOrderPaymentEntryCreate(BaseModel):
    milestone_name: str = Field(min_length=1, max_length=200)
    amount_received: float = Field(gt=0)
    received_date: date
    # Part L "Statutory": "GST-TDS 2% by government/PSU payer" -- the
    # actual amount THIS payment's TDS certificate shows was withheld,
    # PM/Director-entered like every other figure here, not app-computed
    # (see WorkOrderPaymentEntry's own docstring for the retirement-
    # override rationale). Optional: most private-client work orders have
    # none.
    gst_tds_amount: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class WorkOrderPaymentEntryOut(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    milestone_name: str
    amount_received: float
    received_date: date
    gst_tds_amount: float | None
    notes: str | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@work_orders_router.post(
    "/work-orders/{work_order_id}/payment-entries", response_model=WorkOrderPaymentEntryOut, status_code=201
)
def add_payment_entry(
    work_order_id: uuid.UUID,
    payload: WorkOrderPaymentEntryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """Not a blueprint-named entity -- Part L's 'milestone billing (RA
    bills)' has no specified fields anywhere; this is the 'simple
    reconciliation entry (milestone, amount received, date)' Part O's own
    BILLING note allows in place of a fabricated RA-bill schema."""
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work Order not found")

    entry = WorkOrderPaymentEntry(
        work_order_id=work_order_id,
        created_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@work_orders_router.get(
    "/work-orders/{work_order_id}/payment-entries", response_model=list[WorkOrderPaymentEntryOut]
)
def list_payment_entries(
    work_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work Order not found")
    return (
        db.query(WorkOrderPaymentEntry)
        .filter(WorkOrderPaymentEntry.work_order_id == work_order_id)
        .order_by(WorkOrderPaymentEntry.received_date)
        .all()
    )
