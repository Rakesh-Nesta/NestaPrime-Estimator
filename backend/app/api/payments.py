import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.work_order import WorkOrderStatus
from app.services import payments as payments_service

router = APIRouter(prefix="/payments", tags=["payments"])

# Amendment 50 (Section 54): Payments are read by PM/Director (who also write
# them, via work_orders.py) and, read-only, by ca_tax for TDS reconciliation.
# Sales, procurement and site_engineer are refused -- the header is hidden for
# them, so there is nothing to show.
READ_ROLES = ("pm", "director", "ca_tax")


class PaymentRowOut(BaseModel):
    work_order_id: uuid.UUID
    project_id: uuid.UUID
    project_no: str
    client_name: str
    quotation_document_no: str
    work_order_status: WorkOrderStatus
    awarded_at: datetime
    order_value: float
    total_received: float
    total_tds: float
    outstanding: float
    over_received: bool
    milestone_count: int
    milestones_total: float
    next_due_date: date | None
    overdue_amount: float
    overdue: bool
    overdue_milestones_count: int


@router.get("", response_model=list[PaymentRowOut])
def list_payments(
    overdue: bool | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """One row per Work Order, overdue first. `overdue=true` keeps only Work
    Orders with at least one unpaid milestone past its due date; `search`
    matches project number or client name."""
    rows = payments_service.build_rows(db, date.today())
    if overdue is True:
        rows = [r for r in rows if r["overdue"]]
    elif overdue is False:
        rows = [r for r in rows if not r["overdue"]]
    if search:
        needle = search.strip().lower()
        rows = [r for r in rows if needle in r["project_no"].lower() or needle in r["client_name"].lower()]
    return payments_service.sort_rows(rows)
