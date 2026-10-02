import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PdfImageExclusion(Base):
    """A user's explicit decision to leave ONE stored image out of ONE generated document (an Estimate or a Quotation
    revision). It is a separate record, never a flag on the Attachment: the attachment, its file and its hash are untouched,
    other documents that use the same image are unaffected, and the decision is attributable and audited. doc_id is the
    specific document row, so a new revision (a new row) starts with no exclusions."""

    __tablename__ = "pdf_image_exclusions"
    __table_args__ = (UniqueConstraint("doc_type", "doc_id", "attachment_id", name="uq_pdf_image_exclusion"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "estimate" | "quotation"
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=False)
    excluded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    excluded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
