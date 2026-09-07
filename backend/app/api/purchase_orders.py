import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetLine
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus
from app.models.vendor import Vendor

purchase_orders_router = APIRouter(tags=["purchase-orders"])

PROCUREMENT_ROLES = ("pm", "director", "procurement")


def _get_cost_sheet(db: Session, cost_sheet_id: uuid.UUID) -> CostSheet:
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    return cost_sheet


def _po_number(db: Session, project_no: str) -> str:
    """POs aren't revisioned documents like CS/EST/NPQ (M.2 rule 10) --
    just sequentially numbered per project: PO-2609-0043-01, -02, ..."""
    suffix = project_no.split("-", 1)[1]
    prefix = f"PO-{suffix}-"
    existing = db.query(PurchaseOrder).filter(PurchaseOrder.po_no.like(f"{prefix}%")).count()
    return f"{prefix}{existing + 1:02d}"


def _get_open_po_line_cost_sheet_line_ids(db: Session, cost_sheet_id: uuid.UUID) -> set[uuid.UUID]:
    """A CostSheetLine already on a non-cancelled PO can't be raised
    again -- Part O's flat schema has no split-sourcing model (see the
    PurchaseOrderLine docstring)."""
    rows = (
        db.query(PurchaseOrderLine.cost_sheet_line_id)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .filter(
            PurchaseOrder.cost_sheet_id == cost_sheet_id,
            PurchaseOrder.status != PurchaseOrderStatus.CANCELLED,
        )
        .all()
    )
    return {row[0] for row in rows}


class PurchaseOrderLineCreate(BaseModel):
    cost_sheet_line_id: uuid.UUID
    quantity: float = Field(gt=0)
    rate: float = Field(gt=0)


class PurchaseOrderCreate(BaseModel):
    vendor_id: uuid.UUID
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)
    delivery_date: date | None = None
    eway_bill_no: str | None = None


class PurchaseOrderLineOut(BaseModel):
    id: uuid.UUID
    cost_sheet_line_id: uuid.UUID
    item_name: str
    unit: str
    quantity: float
    rate: float
    amount: float
    received_qty: float
    balance_qty: float

    model_config = ConfigDict(from_attributes=True)


def _line_to_out(line: PurchaseOrderLine) -> PurchaseOrderLineOut:
    return PurchaseOrderLineOut(
        id=line.id,
        cost_sheet_line_id=line.cost_sheet_line_id,
        item_name=line.item_name,
        unit=line.unit,
        quantity=float(line.quantity),
        rate=float(line.rate),
        amount=float(line.quantity) * float(line.rate),
        received_qty=float(line.received_qty),
        balance_qty=float(line.quantity) - float(line.received_qty),
    )


class PurchaseOrderOut(BaseModel):
    id: uuid.UUID
    po_no: str
    cost_sheet_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    status: PurchaseOrderStatus
    delivery_date: date | None
    eway_bill_no: str | None
    lines: list[PurchaseOrderLineOut]
    created_at: datetime


def _po_to_out(po: PurchaseOrder, vendor_name: str, lines: list[PurchaseOrderLine]) -> PurchaseOrderOut:
    return PurchaseOrderOut(
        id=po.id,
        po_no=po.po_no,
        cost_sheet_id=po.cost_sheet_id,
        vendor_id=po.vendor_id,
        vendor_name=vendor_name,
        status=po.status,
        delivery_date=po.delivery_date,
        eway_bill_no=po.eway_bill_no,
        lines=[_line_to_out(line) for line in lines],
        created_at=po.created_at,
    )


def _get_po_with_lines(db: Session, po_id: uuid.UUID) -> tuple[PurchaseOrder, list[PurchaseOrderLine]]:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id == po_id).all()
    return po, lines


@purchase_orders_router.post(
    "/cost-sheets/{cost_sheet_id}/purchase-orders", response_model=PurchaseOrderOut, status_code=201
)
def create_purchase_order(
    cost_sheet_id: uuid.UUID,
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    """Raises a PO for one or more of this Cost Sheet's own lines --
    item_name/unit are copied (frozen) from the CostSheetLine at creation
    time; rate is the vendor's own quoted rate, not necessarily the Cost
    Sheet's estimate rate."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
    vendor = db.query(Vendor).filter(Vendor.id == payload.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    already_on_a_po = _get_open_po_line_cost_sheet_line_ids(db, cost_sheet_id)
    resolved_lines: list[tuple[CostSheetLine, PurchaseOrderLineCreate]] = []
    for line_in in payload.lines:
        cs_line = (
            db.query(CostSheetLine)
            .filter(CostSheetLine.id == line_in.cost_sheet_line_id, CostSheetLine.cost_sheet_id == cost_sheet_id)
            .first()
        )
        if not cs_line:
            raise HTTPException(status_code=404, detail=f"Cost sheet line {line_in.cost_sheet_line_id} not found")
        if cs_line.id in already_on_a_po:
            raise HTTPException(
                status_code=400, detail=f"Cost sheet line '{cs_line.item_name}' is already on an open PO"
            )
        resolved_lines.append((cs_line, line_in))

    po = PurchaseOrder(
        po_no=_po_number(db, project.project_no),
        cost_sheet_id=cost_sheet_id,
        vendor_id=payload.vendor_id,
        status=PurchaseOrderStatus.DRAFT,
        delivery_date=payload.delivery_date,
        eway_bill_no=payload.eway_bill_no,
        created_by_id=current_user.id,
    )
    db.add(po)
    db.flush()

    lines_to_create = [
        PurchaseOrderLine(
            purchase_order_id=po.id,
            cost_sheet_line_id=cs_line.id,
            item_name=cs_line.item_name,
            unit=cs_line.unit,
            quantity=line_in.quantity,
            rate=line_in.rate,
        )
        for cs_line, line_in in resolved_lines
    ]
    db.add_all(lines_to_create)
    db.commit()
    db.refresh(po)

    return _po_to_out(po, vendor.name, lines_to_create)


@purchase_orders_router.get(
    "/cost-sheets/{cost_sheet_id}/purchase-orders", response_model=list[PurchaseOrderOut]
)
def list_purchase_orders(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    _get_cost_sheet(db, cost_sheet_id)
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.cost_sheet_id == cost_sheet_id).all()
    out = []
    for po in pos:
        vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
        lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.purchase_order_id == po.id).all()
        out.append(_po_to_out(po, vendor.name, lines))
    return out


@purchase_orders_router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(
    po_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    po, lines = _get_po_with_lines(db, po_id)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    return _po_to_out(po, vendor.name, lines)


@purchase_orders_router.post("/purchase-orders/{po_id}/issue", response_model=PurchaseOrderOut)
def issue_purchase_order(
    po_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    po, lines = _get_po_with_lines(db, po_id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only a Draft purchase order can be issued")
    po.status = PurchaseOrderStatus.ISSUED
    db.commit()
    db.refresh(po)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    return _po_to_out(po, vendor.name, lines)


@purchase_orders_router.post("/purchase-orders/{po_id}/cancel", response_model=PurchaseOrderOut)
def cancel_purchase_order(
    po_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    po, lines = _get_po_with_lines(db, po_id)
    if po.status == PurchaseOrderStatus.RECEIVED:
        raise HTTPException(status_code=400, detail="A fully received purchase order cannot be cancelled")
    po.status = PurchaseOrderStatus.CANCELLED
    db.commit()
    db.refresh(po)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    return _po_to_out(po, vendor.name, lines)


class ReceiveLineIn(BaseModel):
    line_id: uuid.UUID
    received_qty: float = Field(ge=0)


class ReceivePayload(BaseModel):
    lines: list[ReceiveLineIn] = Field(min_length=1)


@purchase_orders_router.post("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderOut)
def receive_purchase_order(
    po_id: uuid.UUID,
    payload: ReceivePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    """Records delivered quantity per line; status derives from the
    lines' own received_qty vs quantity -- Received only once every line
    is fully in, Partially received as soon as any of it has arrived."""
    po, lines = _get_po_with_lines(db, po_id)
    if po.status not in (PurchaseOrderStatus.ISSUED, PurchaseOrderStatus.PARTIALLY_RECEIVED):
        raise HTTPException(status_code=400, detail="Only an Issued purchase order can receive material")

    lines_by_id = {line.id: line for line in lines}
    for update in payload.lines:
        line = lines_by_id.get(update.line_id)
        if not line:
            raise HTTPException(status_code=404, detail=f"PO line {update.line_id} not found on this order")
        if update.received_qty > float(line.quantity):
            raise HTTPException(
                status_code=422, detail=f"Received qty for '{line.item_name}' exceeds the ordered quantity"
            )
        line.received_qty = update.received_qty

    if all(float(line.received_qty) >= float(line.quantity) for line in lines):
        po.status = PurchaseOrderStatus.RECEIVED
    elif any(float(line.received_qty) > 0 for line in lines):
        po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED

    db.commit()
    db.refresh(po)
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    return _po_to_out(po, vendor.name, lines)
