import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TechnicalBidChecklistKey(str, enum.Enum):
    """Part L 'Documents' row: 'Technical bid checklist (GST, PAN,
    turnover, past work certificates, ISO)' -- this five-item list is the
    complete, verbatim specification; nothing else about the checklist
    (required/optional, per-item type, workflow) is stated anywhere in
    the blueprint. Inferred (not stated) to be NestaPrime's OWN bidder-
    eligibility documents: Part O's COMPANY/COMPANY_REGISTRATIONS entities
    already model NestaPrime's own PAN/turnover/GSTIN, while the client's
    GST/PAN are separately modeled on CLIENTS -- 'past work certificates'
    and 'ISO' have no home anywhere else in the blueprint, so nothing
    further is invented for either."""

    GST = "gst"
    PAN = "pan"
    TURNOVER = "turnover"
    PAST_WORK_CERTIFICATES = "past_work_certificates"
    ISO = "iso"


class TechnicalBidChecklistItem(Base):
    """One row per (project, checklist key) -- five rows per Tender Mode
    project, lazily created on first read (see
    get_technical_bid_checklist in app/api/tender.py). 'confirmed' plus an
    optional attachment (via the existing generic Attachment system,
    doc_type=TECHNICAL_BID_CHECKLIST_ITEM) is the plainest, least-invented
    way to track a checklist item -- the blueprint gives no required/
    optional flag, no per-item data type, and no workflow/gating
    description, so none is fabricated here."""

    __tablename__ = "technical_bid_checklist_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    key: Mapped[TechnicalBidChecklistKey] = mapped_column(
        Enum(TechnicalBidChecklistKey, name="technical_bid_checklist_key"), nullable=False
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
