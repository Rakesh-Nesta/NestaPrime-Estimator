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
    TELEGRAM = "telegram"


class MessageStatus(str, enum.Enum):
    """Amendment 8 (Section 8): WhatsApp (via the self-hosted wa-gateway)
    and Telegram (via the Bot API) are real, wired-up sends -- RECORDED
    for a create with no send attempt (email, still log-only, unchanged),
    SENT once the provider accepts it, FAILED on a provider/network
    error. DELIVERED stays unused: wa-gateway only ever confirms
    "sent" (Baileys' delivery/read receipts aren't exposed), and
    Telegram's Bot API gives no delivery/read signal for outbound
    messages either -- so this build never claims a delivery status it
    can't actually verify. The value is kept defined for a future
    provider (e.g. a real WhatsApp BSP) that can report it truthfully."""

    RECORDED = "recorded"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class Message(Base):
    """Part O MESSAGES / M.7.2 rule 1: 'Every send creates a MESSAGES
    record: document id and revision, channel, recipient, sender,
    template used, attachment hash..., provider message id, delivery
    status.' Amendment 8 (Section 8) wired up real sending for WhatsApp
    (self-hosted wa-gateway) and Telegram (Bot API) -- status/
    provider_message_id are populated for real for those two channels.
    Email has no provider wired up (no SMTP account) and stays exactly
    as before: every email row is a manually confirmed 'this was sent'
    record (status=recorded), never a provider-verified receipt.
    doc_type/doc_id is the same polymorphic reference pattern Attachment
    uses (Cost Sheet, Estimate or Quotation)."""

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
    # The provider's own id for this send (WhatsApp message id via
    # wa-gateway, Telegram's message_id) -- null for email (no provider)
    # and for a WhatsApp/Telegram send that FAILED before the provider
    # ever returned one.
    provider_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
