import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.setting import DocumentType


class AttachmentTag(str, enum.Enum):
    """Part O ATTACHMENTS.tag -- the full enum, though M.3 only names a
    subset per stage (Cost Sheet: site photos/survey form/vendor quotes/
    soil report; Estimate: product images/client approval or demand
    evidence; Quotation: signed quotation/PO/GST certificate)."""

    APPROVAL_EVIDENCE = "approval_evidence"
    CLIENT_DEMAND = "client_demand"
    GST_OPINION = "gst_opinion"
    STRUCTURAL_DESIGN = "structural_design"
    SOIL_REPORT = "soil_report"
    SURVEY_FORM = "survey_form"
    VENDOR_QUOTE = "vendor_quote"
    DRAWING = "drawing"
    PHOTO = "photo"
    PRODUCT_IMAGE = "product_image"
    SIGNED_DOCUMENT = "signed_document"
    DELIVERY_CHALLAN = "delivery_challan"
    INVOICE = "invoice"
    REFERENCE = "reference"


class ApprovalStrength(str, enum.Enum):
    """M.3: 'Formal (e-signed ... signed scan ... purchase/work order ...)
    or Informal (WhatsApp/email screenshot with timestamp and sender
    visible).' Only meaningful on an approval_evidence-tagged attachment."""

    FORMAL = "formal"
    INFORMAL = "informal"


class Attachment(Base):
    """Part O ATTACHMENTS / M.3. 'Every attachment is stored write-once (no
    overwrite, no delete -- only supersede) with its SHA-256 hash,
    uploader, timestamp and IP.' doc_type/doc_id is a polymorphic reference
    (Cost Sheet, Estimate or Quotation -- Actuals/Work Order has no backing
    entity yet, so it isn't a valid doc_type here). Image auto-compression
    to a <=5MB preview (M.3) is a documented gap -- it needs an image
    library (e.g. Pillow) this project doesn't otherwise depend on; every
    file is stored and served at its original size for now."""

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Reuses Override's own enum type (Part Q) -- Postgres knows it as
    # "override_document_type", not a generic "document_type".
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="override_document_type"), nullable=False
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_size: Mapped[int] = mapped_column(Integer, nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    tag: Mapped[AttachmentTag] = mapped_column(Enum(AttachmentTag, name="attachment_tag"), nullable=False)
    approval_strength: Mapped[ApprovalStrength | None] = mapped_column(
        Enum(ApprovalStrength, name="approval_strength"), nullable=True
    )

    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Write-once evidence integrity: a "re-upload" always inserts a new
    # row (version = previous + 1) and points the old row's
    # superseded_by_id at it -- the old row is never edited or deleted.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
