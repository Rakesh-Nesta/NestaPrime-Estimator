import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PurchaseOrder(Base):
    """Part O PURCHASE_ORDERS: 'po_no, vendor_id, bom lines, qty, rate,
    delivery date, eway_bill_no, received qty, status.' Tied to one Cost
    Sheet (its BOM/consumption sheet is where the lines come from) rather
    than the Quotation -- procurement runs off the Cost Sheet's own
    material list, matching J.3/J.4's own scoping.

    No WhatsApp/email send here (M.7's vendor RFQ/PO flow stays out of
    scope by the same explicit choice as the rest of Communications) --
    this is the entity plus manual create/issue/receive lifecycle only."""

    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    cost_sheet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_sheets.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, name="purchase_order_status"), default=PurchaseOrderStatus.DRAFT, nullable=False
    )
    delivery_date: Mapped[date | None] = mapped_column(DateTime, nullable=True)
    eway_bill_no: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class PurchaseOrderLine(Base):
    """One BOM item on a PO. item_name/unit are copied from the
    CostSheetLine at PO-creation time -- frozen, like every other document
    in this app (M.2 rule 5) -- so a PO stays readable even if the
    underlying Cost Sheet line is later edited or removed. rate is the
    vendor's quoted rate, which may differ from the Cost Sheet's own
    estimate rate.

    One CostSheetLine can be attached to at most one (non-cancelled) PO
    line -- Part O's flat schema gives no split-sourcing model, so
    splitting one BOM item's quantity across multiple vendors/POs isn't
    supported in this version, enforced at the API rather than guessed."""

    __tablename__ = "purchase_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False
    )
    cost_sheet_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_sheet_lines.id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(14, 3), default=0, nullable=False)
