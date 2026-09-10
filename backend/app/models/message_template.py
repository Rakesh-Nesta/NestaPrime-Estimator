import enum
import uuid

from sqlalchemy import Boolean, Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.message import MessageChannel
from app.models.setting import DocumentType


class WhatsappTemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class MessageTemplate(Base):
    """Part O MESSAGE_TEMPLATES / M.7.2 rule 6: 'Director-managed library
    of message templates per document and channel (subject, body,
    placeholders such as client name, quotation number, amount, validity,
    sender). WhatsApp templates are submitted to Meta for approval
    through the provider; only approved templates are used for
    business-initiated messages.'

    Distinct from Message.template_key -- a free-text tag this build's
    own automatic internal notifications set (e.g.
    'structural_rebase_required' on the E.5 rebase-notify flow),
    unrelated to this Director-managed library. document_type is
    nullable: some templates (a payment reminder, a generic vendor
    follow-up) aren't tied to one specific document type.

    No real email/WhatsApp provider is wired up in this build (see
    Message's own docstring) -- sending is still a PM's own manual
    action outside the app, with nothing that would ever consume a
    rendered placeholder. So this library supplies the Meta-approved
    wording and its approval gate, not live substitution: {client_name} /
    {quotation_number} / {amount} / {validity} stay literal placeholder
    text in body for the sender to fill in by hand -- the same honesty as
    every other feature this codebase leaves manual when the automatable
    part needs infrastructure this build doesn't have.

    whatsapp_template_status only applies when channel is WHATSAPP (Meta
    approval has no email equivalent); it stays null for an email
    template. version increments on every subject/body edit; editing a
    submitted or approved WhatsApp template's content resets its status
    back to draft, since Meta's approval is tied to specific wording."""

    __tablename__ = "message_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type: Mapped[DocumentType | None] = mapped_column(
        Enum(DocumentType, name="override_document_type"), nullable=True
    )
    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel, name="message_channel"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_template_status: Mapped[WhatsappTemplateStatus | None] = mapped_column(
        Enum(WhatsappTemplateStatus, name="whatsapp_template_status"), nullable=True
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("name", "channel", name="uq_message_template_name_channel"),)
