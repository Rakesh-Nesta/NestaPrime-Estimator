import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.payments import PaymentRowOut
from app.core import p5
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import Quotation, QuotationStatus
from app.models.work_order import (
    WorkOrder,
    WorkOrderPaymentEntry,
    WorkOrderPaymentMilestone,
    WorkOrderStatus,
)
from app.services import payments as payments_service

work_orders_router = APIRouter(tags=["work-orders"])

# M.1 stage 4 ("Work Order & Actuals") lists only PM/Director in its role
# column -- unlike the Estimate/Quotation stages, Sales has no role here.
ROLES = ("pm", "director")
# Amendment 50 (Section 54): ca_tax may READ payment data (reconciling TDS)
# but never change it; every write stays PM/Director.
READ_ROLES = ("pm", "director", "ca_tax")

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
    if not db.query(Quotation.id).filter(Quotation.id == quotation_id).first():
        raise HTTPException(status_code=404, detail="Quotation not found")
    try:
        # P5 contract revision 7, Section 4.4: take the shared lock order (Project -> Quotation ->
        # Agreement -> Authorization -> TeamMember -> User) and re-check everything LIVE under it, so a
        # concurrent void/correction/removal/deactivation either commits first (and this refuses) or
        # waits until this Work Order exists (which it then leaves untouched).
        scope = p5.lock_quotation_scope(db, quotation_id, with_team=True)
        quotation = scope.quotation
        if quotation.status != QuotationStatus.WON:
            raise HTTPException(status_code=400, detail="A Work Order can only be created once the Quotation is Won")

        existing = db.query(WorkOrder).filter(WorkOrder.quotation_id == quotation_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="A Work Order already exists for this Quotation")

        p5.require_work_order_authorization(db, quotation, scope)

        work_order = WorkOrder(
            project_id=quotation.project_id,
            quotation_id=quotation_id,
            created_by_id=current_user.id,
        )
        db.add(work_order)
        db.commit()
    except BaseException:
        db.rollback()
        raise
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
    # Amendment 50: optionally which expected payment this receipt is against.
    milestone_id: uuid.UUID | None = None


class WorkOrderPaymentEntryOut(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    milestone_name: str
    amount_received: float
    received_date: date
    gst_tds_amount: float | None
    notes: str | None
    milestone_id: uuid.UUID | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkOrderPaymentEntryUpdate(BaseModel):
    """Amendment 50: a mistyped receipt is corrected by editing it (audit-
    logged with old and new values); receipts are never deleted. Only the
    fields sent are changed; sending milestone_id null unlinks the receipt."""

    milestone_name: str | None = Field(default=None, min_length=1, max_length=200)
    amount_received: float | None = Field(default=None, gt=0)
    received_date: date | None = None
    gst_tds_amount: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    milestone_id: uuid.UUID | None = None


def _linked_milestone_or_400(db: Session, milestone_id: uuid.UUID | None, work_order_id: uuid.UUID) -> None:
    """A receipt may only be recorded against a milestone of its own Work Order."""
    if milestone_id is None:
        return
    milestone = db.query(WorkOrderPaymentMilestone).filter(WorkOrderPaymentMilestone.id == milestone_id).first()
    if milestone is None or milestone.work_order_id != work_order_id:
        raise HTTPException(status_code=400, detail="That milestone does not belong to this Work Order")


@work_orders_router.post(
    "/work-orders/{work_order_id}/payment-entries", response_model=WorkOrderPaymentEntryOut, status_code=201
)
def add_payment_entry(
    work_order_id: uuid.UUID,
    payload: WorkOrderPaymentEntryCreate,
    request: Request,
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

    _linked_milestone_or_400(db, payload.milestone_id, work_order_id)

    entry = WorkOrderPaymentEntry(
        work_order_id=work_order_id,
        created_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(entry)
    db.flush()
    # Amendment 50: a receipt is a money figure, so recording one is audit-
    # logged (the one-line "created" convention client_signatories/users use).
    write_audit_log_entry(
        db, current_user, "work_order_payment_entry", entry.id, "created",
        old_value=None, new_value=f"{entry.milestone_name}: {payload.amount_received}", request=request,
    )
    db.commit()
    db.refresh(entry)
    return entry


@work_orders_router.get(
    "/work-orders/{work_order_id}/payment-entries", response_model=list[WorkOrderPaymentEntryOut]
)
def list_payment_entries(
    work_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
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


# ---------------------------------------------------------------------------
# Amendment 50 (Section 54): expected payments (milestones), receipt edits and
# the per-Work-Order summary. Everything shown is derived by
# app.services.payments from figures a person entered; nothing is stored or
# inferred, and this never computes GST, TDS or invoices.
# ---------------------------------------------------------------------------


class PaymentMilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    amount_due: float = Field(gt=0)
    due_date: date
    notes: str | None = Field(default=None, max_length=500)


class PaymentMilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    amount_due: float | None = Field(default=None, gt=0)
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class PaymentMilestoneOut(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    name: str
    amount_due: float
    due_date: date
    notes: str | None
    received_amount: float
    tds_amount: float
    settled_amount: float
    outstanding_amount: float
    status: str
    overdue: bool
    created_by_id: uuid.UUID
    created_at: datetime


def _audit_value(old_value, new_value):
    """Money columns come back as Decimal ("12345.00") but arrive as float
    (12000.0); log both in the same two-decimal form so the trail reads
    consistently."""
    if isinstance(old_value, Decimal) and new_value is not None:
        return f"{Decimal(str(new_value)):.2f}"
    return new_value


def _get_work_order_or_404(db: Session, work_order_id: uuid.UUID) -> WorkOrder:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work Order not found")
    return work_order


def _lock_work_order_or_404(db: Session, work_order_id: uuid.UUID) -> WorkOrder:
    """The common Work Order locking protocol for EVERY payment-milestone write (create, edit, delete).

    A milestone write must (1) take this lock, (2) only then re-read the state it depends on (the other milestones,
    the milestone being edited or deleted), (3) validate against the cap, (4) mutate and write its audit entry, and
    (5) commit -- all in one transaction, so the lock is held until the commit or rollback and is released by either
    (a refused or failed request is rolled back by the request's session closing, app/db/session.py get_db).

    Why a lock on the Work Order row: the cap ("milestones may not total more than the order value", Section 54
    item 4) is a property of ALL of a Work Order's milestones, so writers of different milestones of one Work Order
    must serialise; writers of different Work Orders do not contend.

    Lock mode: SELECT ... FOR NO KEY UPDATE (SQLAlchemy `with_for_update(key_share=True)`). In PostgreSQL that mode
    conflicts with FOR UPDATE, FOR NO KEY UPDATE and FOR SHARE, and does NOT conflict with FOR KEY SHARE. So: (a) two
    milestone writers on one Work Order exclude each other; (b) the foreign-key checks that a receipt insert or any
    other child insert makes against this Work Order row (FOR KEY SHARE) are NOT blocked, so receipt writes proceed
    (covered by a test); (c) an ordinary UPDATE of this row that does not touch its key, such as a Work Order status
    change, takes the same mode and therefore waits for an in-flight milestone write, and vice versa -- briefly, and
    harmlessly.

    Deadlock reasoning (by inspection of the current code and by the tests, not a proof): this is the only EXPLICIT
    row lock these paths take, and no explicit lock is requested after it. The audit and milestone inserts then take
    implicit FOR KEY SHARE locks on parent rows (for example the acting user); no other code path holds a stronger lock
    on such a row while waiting for a Work Order lock -- P5's explicit lock order (Project, Quotation, Agreement,
    Authorization, TeamMember, User, Attachment) never locks Work Order rows, and receipt and status paths do not wait
    on this lock while holding anything these paths need. A new code path that locks Work Order rows explicitly must
    be placed in that order deliberately.

    populate_existing makes the read return the row as it is NOW (after any wait), even if it was loaded earlier in
    the session; the other reads that follow (the milestones) are fresh queries in the same transaction."""
    work_order = db.execute(
        select(WorkOrder)
        .where(WorkOrder.id == work_order_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work Order not found")
    return work_order


def _locked_milestone_or_404(db: Session, milestone_id: uuid.UUID) -> tuple[WorkOrderPaymentMilestone, WorkOrder]:
    """Locate a milestone, take its Work Order's lock, then RE-READ the milestone under the lock. The first read is
    only used to learn the (immutable) work_order_id; if the milestone was deleted while this request waited for the
    lock, the re-read finds nothing and the request gets the same 404 as for any missing milestone."""
    first = db.query(WorkOrderPaymentMilestone.work_order_id).filter(WorkOrderPaymentMilestone.id == milestone_id).first()
    if first is None:
        raise HTTPException(status_code=404, detail="Payment milestone not found")
    work_order = _lock_work_order_or_404(db, first[0])
    milestone = db.execute(
        select(WorkOrderPaymentMilestone)
        .where(WorkOrderPaymentMilestone.id == milestone_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="Payment milestone not found")
    return milestone, work_order


def _milestone_out(db: Session, milestone: WorkOrderPaymentMilestone) -> dict:
    derived = payments_service.milestones_for_work_order(db, milestone.work_order_id, date.today())
    return next(m for m in derived if m["id"] == milestone.id)


def _check_milestone_cap(
    db: Session, work_order: WorkOrder, amount: float, exclude_id: uuid.UUID | None = None
) -> None:
    """The milestones of a Work Order may not total more than its order value
    (the Won Quotation's frozen, GST-inclusive quotation_total). Receipts are
    NOT capped -- advances and extra work are shown as over-received."""
    value = payments_service.order_value(db, work_order)
    query = db.query(WorkOrderPaymentMilestone).filter(WorkOrderPaymentMilestone.work_order_id == work_order.id)
    if exclude_id is not None:
        query = query.filter(WorkOrderPaymentMilestone.id != exclude_id)
    others = sum((Decimal(str(m.amount_due)) for m in query.all()), Decimal("0"))
    total = others + Decimal(str(amount))
    if total > value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Milestones would total Rs {total:,.2f}, more than this Work Order's value "
                f"of Rs {value:,.2f}"
            ),
        )


@work_orders_router.post(
    "/work-orders/{work_order_id}/payment-milestones", response_model=PaymentMilestoneOut, status_code=201
)
def add_payment_milestone(
    work_order_id: uuid.UUID,
    payload: PaymentMilestoneCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    work_order = _lock_work_order_or_404(db, work_order_id)  # lock first, then re-read and validate
    _check_milestone_cap(db, work_order, payload.amount_due)

    milestone = WorkOrderPaymentMilestone(
        work_order_id=work_order_id, created_by_id=current_user.id, **payload.model_dump()
    )
    db.add(milestone)
    db.flush()
    write_audit_log_entry(
        db, current_user, "work_order_payment_milestone", milestone.id, "created",
        old_value=None, new_value=f"{milestone.name}: {payload.amount_due} due {payload.due_date}", request=request,
    )
    db.commit()
    db.refresh(milestone)
    return _milestone_out(db, milestone)


@work_orders_router.get(
    "/work-orders/{work_order_id}/payment-milestones", response_model=list[PaymentMilestoneOut]
)
def list_payment_milestones(
    work_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    _get_work_order_or_404(db, work_order_id)
    return payments_service.milestones_for_work_order(db, work_order_id, date.today())


@work_orders_router.patch("/payment-milestones/{milestone_id}", response_model=PaymentMilestoneOut)
def update_payment_milestone(
    milestone_id: uuid.UUID,
    payload: PaymentMilestoneUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    milestone, work_order = _locked_milestone_or_404(db, milestone_id)  # lock first, then re-read and validate

    changes = payload.model_dump(exclude_unset=True)
    for required in ("name", "amount_due", "due_date"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=400, detail=f"{required} cannot be cleared")
    if "amount_due" in changes:
        _check_milestone_cap(db, work_order, changes["amount_due"], exclude_id=milestone.id)

    for field, value in changes.items():
        old_value = getattr(milestone, field)
        if isinstance(old_value, Decimal) and value is not None:
            unchanged = old_value == Decimal(str(value))
        else:
            unchanged = old_value == value
        if not unchanged:
            write_audit_log_entry(
                db, current_user, "work_order_payment_milestone", milestone.id, field,
                old_value=old_value, new_value=_audit_value(old_value, value), request=request,
            )
        setattr(milestone, field, value)
    db.commit()
    db.refresh(milestone)
    return _milestone_out(db, milestone)


@work_orders_router.delete("/payment-milestones/{milestone_id}", status_code=204)
def delete_payment_milestone(
    milestone_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """A milestone is only a promise, so it can be deleted -- but not while
    receipts are recorded against it, which would silently orphan them.
    Unlink those receipts first (PATCH /payment-entries/{id})."""
    milestone, _work_order = _locked_milestone_or_404(db, milestone_id)  # lock first, then re-read and validate
    linked = db.query(WorkOrderPaymentEntry).filter(WorkOrderPaymentEntry.milestone_id == milestone_id).count()
    if linked:
        raise HTTPException(
            status_code=400,
            detail=f"{linked} receipt(s) are recorded against this milestone -- unlink them before deleting it",
        )
    write_audit_log_entry(
        db, current_user, "work_order_payment_milestone", milestone.id, "deleted",
        old_value=f"{milestone.name}: {milestone.amount_due} due {milestone.due_date}", new_value=None,
        request=request,
    )
    db.delete(milestone)
    db.commit()


@work_orders_router.patch("/payment-entries/{entry_id}", response_model=WorkOrderPaymentEntryOut)
def update_payment_entry(
    entry_id: uuid.UUID,
    payload: WorkOrderPaymentEntryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    entry = db.query(WorkOrderPaymentEntry).filter(WorkOrderPaymentEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payment entry not found")

    changes = payload.model_dump(exclude_unset=True)
    for required in ("milestone_name", "amount_received", "received_date"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=400, detail=f"{required} cannot be cleared")
    if "milestone_id" in changes:
        _linked_milestone_or_400(db, changes["milestone_id"], entry.work_order_id)

    for field, value in changes.items():
        old_value = getattr(entry, field)
        # Numeric columns come back as Decimal; compare as numbers so an
        # unchanged amount does not write a spurious audit row.
        if isinstance(old_value, Decimal) and value is not None:
            unchanged = old_value == Decimal(str(value))
        else:
            unchanged = old_value == value
        if not unchanged:
            write_audit_log_entry(
                db, current_user, "work_order_payment_entry", entry.id, field,
                old_value=old_value, new_value=_audit_value(old_value, value), request=request,
            )
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@work_orders_router.get(
    "/work-orders/{work_order_id}/payment-summary", response_model=PaymentRowOut
)
def get_payment_summary(
    work_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """The same row `GET /payments` returns for this Work Order, for the
    Documents screen's Work Order panel."""
    _get_work_order_or_404(db, work_order_id)
    rows = payments_service.build_rows(db, date.today(), [work_order_id])
    return rows[0]
