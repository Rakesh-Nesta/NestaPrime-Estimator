import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OpportunityStage(str, enum.Enum):
    """Amendment 44 (Section E step 5): a Lead/Opportunity's pipeline
    stage, distinct from Client -- see Opportunity's own docstring for why
    these are two entities. Won/Lost are terminal, same shape as
    QuotationStatus's own Won/Lost."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    WON = "won"
    LOST = "lost"


TERMINAL_STAGES = (OpportunityStage.WON, OpportunityStage.LOST)


class Opportunity(Base):
    """Amendment 44 (Section E step 5, Director design input 2026-09-23
    against the CRM reference's "Leads" tab): a pre-project lead/enquiry,
    genuinely distinct from Client, not a status flag on it. client_id is
    nullable -- a raw enquiry ("Add Enquiry") starts with just
    lead_name/lead_phone/lead_email, since Client.type is mandatory and
    forcing that full form at first contact is itself the friction point
    the design input calls out. Once qualified, it can be linked to an
    existing Client (see PATCH .../link-client) -- linking, not an
    automatic promotion that creates one.

    next_follow_up_date is nullable at the column level only so a WON/LOST
    (terminal) stage can clear it -- while an Opportunity is still open,
    the API layer (not a DB constraint) enforces the Director's 2026-09-22
    decision that it can never be left null: required at creation and on
    every stage change to a non-terminal stage, distinct from Client's own
    always-optional reminder field of the same name."""

    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )
    lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    lead_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lead_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    stage: Mapped[OpportunityStage] = mapped_column(
        Enum(OpportunityStage, name="opportunity_stage"), default=OpportunityStage.NEW, nullable=False
    )
    # Same shape as Quotation.won_lost_reason -- set only on a LOST transition.
    lost_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    next_follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Set once "Start Project" (item 6 of the spec) creates a Project from
    # a Won, Client-linked Opportunity -- lets Quotations trace back to the
    # Opportunity that produced them (build index step 8) via
    # Project.opportunity_id, the forward half of this same link.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )

    # Doubles as the "owner" field Amendment 43's registration flagged as
    # missing on Client -- same established created_by_id pattern already
    # used on CostSheet/Estimate/Quotation/PriceRequest/PurchaseOrder/
    # SiteSurvey/WorkOrder.
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
