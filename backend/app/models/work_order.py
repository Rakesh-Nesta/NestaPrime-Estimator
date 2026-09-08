import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkOrderStatus(str, enum.Enum):
    AWARDED = "awarded"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class WorkOrder(Base):
    """Part O: 'WORK_ORDERS -- project_no, quotation_id, client work order
    attachment, awarded_at, status (Awarded / In progress / Completed).'
    M.1 stage 4 ('Work Order & Actuals', PM/Director, reached once a
    Quotation is Won per the M.1 diagram: QUOTATION -> WORK ORDER /
    ACTUALS). The 'client work order attachment' is the existing generic
    Attachment system (doc_type=WORK_ORDER, doc_id=this row's id) -- the
    Attachment model's own docstring flagged this as a gap ('Actuals/Work
    Order has no backing entity yet'), now closed. One work order per
    Quotation, matching the blueprint's own field list exactly."""

    __tablename__ = "work_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id"), unique=True, nullable=False
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"), default=WorkOrderStatus.AWARDED, nullable=False
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )


class WorkOrderPaymentEntry(Base):
    """NOT a blueprint-named entity: Part L names 'milestone billing (RA
    bills)' with no fields, no entity and no workflow anywhere else in the
    document. Part O's own BILLING entity note (v5.1.9) says: 'If a
    lightweight payment-tracking record is wanted later -- e.g. milestone,
    amount received, date -- it belongs here as a simple reconciliation
    entry, not as a system computing tax.' This model is exactly that
    reconciliation entry, scoped to a Work Order rather than inventing
    RA-bill-specific fields (GST, retention-per-bill, numbering) nothing
    in the blueprint supports."""

    __tablename__ = "work_order_payment_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=False
    )
    milestone_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_received: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    received_date: Mapped[date] = mapped_column(nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
