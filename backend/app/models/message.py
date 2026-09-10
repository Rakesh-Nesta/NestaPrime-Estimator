import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.setting import DocumentType


class MessageChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class MessageStatus(str, enum.Enum):
    """Only RECORDED is ever written by this build. SENT/DELIVERED/FAILED
    are reserved for when a real email/WhatsApp provider integration
    (SMTP, or a WhatsApp Business API BSP like Gupshup/Interakt) lands
    and can report back an actual delivery outcome -- see Message's own
    docstring."""

    RECORDED = "recorded"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class Message(Base):
    """Part O MESSAGES / M.7.2 rule 1: 'Every send creates a MESSAGES
    record: document id and revision, channel, recipient, sender,
    template used, attachment hash..., provider message id, delivery
    status.' This build has no real email/WhatsApp provider wired up --
    no SMTP account, no WhatsApp Business API (Gupshup/Interakt)
    integration -- so every row here is a manually confirmed 'this was
    sent' record (status=recorded) rather than a provider-verified
    delivery receipt. provider_message_id is intentionally not modelled
    since nothing ever populates it; status never advances past
    RECORDED. doc_type/doc_id is the same polymorphic reference pattern
    Attachment uses (Cost Sheet, Estimate or Quotation)."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="override_document_type"), nullable=False
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel, name="message_channel"), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # M.7.2 rule 6: a real, Director-managed MESSAGE_TEMPLATES row this
    # send used -- distinct from template_key above (this build's own
    # freeform tag for automatic internal notifications).
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_templates.id"), nullable=True
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Which stored file (if any) this message refers to -- optional
    # because most generated PDFs (Estimate/Quotation) are streamed on
    # demand and never saved as an Attachment row.
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )

    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status"), default=MessageStatus.RECORDED, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
