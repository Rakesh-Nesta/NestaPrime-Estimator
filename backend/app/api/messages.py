import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.attachments import _get_document_or_404, _require_doc_type_role, _resolve_client_id
from app.api.settings import get_internal_email_domains
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.client import Client
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.message_template import MessageTemplate, WhatsappTemplateStatus
from app.models.setting import DocumentType

messages_router = APIRouter(prefix="/messages", tags=["messages"])

# Same role split as attachments.py: Cost Sheet stays cost-gated,
# Estimate/Quotation follow the document-editing roles (M.4).
DOCUMENT_ROLES = ("sales", "pm", "director")

# M.7.1's own table: these are the doc types that actually reach the
# client (Estimate/Quotation for product/commercial approval, the Site
# Survey form per the same table's own "Site engineer, client" row).
# Cost Sheet and every other internal doc type never leaves the
# company (M.7.2 rule 7), so there's no client consent question to ask
# for them.
_CLIENT_FACING_DOC_TYPES = (DocumentType.ESTIMATE, DocumentType.QUOTATION, DocumentType.SITE_SURVEY)

# M.7.1's own table: "Cost Sheet, Material Consumption Sheet, internal
# BOM -- Internal only". Material Consumption Sheet and internal BOM
# aren't modelled as their own doc_type in this build (no dedicated
# entity exists for either), so Cost Sheet is the only DocumentType this
# rule currently applies to.
_INTERNAL_DOC_TYPES = (DocumentType.COST_SHEET,)


def _enforce_internal_document_channel(db: Session, doc_type: DocumentType, channel: MessageChannel, recipient: str) -> None:
    """M.7.1 / M.7.2 rule 7: 'Internal documents never go outside ... may
    be emailed only to addresses on the COMPANY domain list and never by
    WhatsApp; the API rejects any other recipient.' Unlike
    _enforce_client_consent (which only cares what the client agreed
    to), this is an absolute gate that applies regardless of role or
    consent -- there is no opt-in that makes it acceptable to WhatsApp a
    Cost Sheet or email it outside the company."""
    if doc_type not in _INTERNAL_DOC_TYPES:
        return
    if channel == MessageChannel.WHATSAPP:
        raise HTTPException(
            status_code=400, detail="Internal documents (Cost Sheet) may never be sent by WhatsApp (M.7.2 rule 7)"
        )
    domain = recipient.rsplit("@", 1)[-1].lower() if "@" in recipient else ""
    if domain not in get_internal_email_domains(db):
        raise HTTPException(
            status_code=400,
            detail=f"'{recipient}' is not on the internal-domain list -- internal documents may only be emailed within the company (M.7.2 rule 7)",
        )


def _enforce_client_consent(db: Session, doc_type: DocumentType, doc_id: uuid.UUID, channel: MessageChannel) -> None:
    """M.7.2 rule 5 (DPDP Act 2023, WhatsApp policy): 'WhatsApp business
    messages are sent only to opted-in numbers ... an opt-out is
    honoured immediately.' Consent lives on the Client record as a
    whole (no separate per-contact CONTACTS table exists, same
    simplification Vendor's own consent fields already use), so this
    checks whether the client this document belongs to has agreed to
    the channel at all -- not whether `recipient` matches a specific
    stored address, since M.7.2 rule 4 explicitly allows a PM-approved
    ad-hoc recipient too."""
    if doc_type not in _CLIENT_FACING_DOC_TYPES:
        return
    client_id = _resolve_client_id(db, doc_type, doc_id)
    if client_id is None:
        return
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        return
    if channel == MessageChannel.WHATSAPP and not client.whatsapp_opt_in:
        raise HTTPException(
            status_code=400,
            detail=f"Client '{client.name}' has not opted in to WhatsApp messages (M.7.2 rule 5)",
        )
    if channel == MessageChannel.EMAIL and not client.email_opt_in:
        raise HTTPException(
            status_code=400,
            detail=f"Client '{client.name}' has opted out of email (M.7.2 rule 5)",
        )


def _resolve_template(
    db: Session, template_id: uuid.UUID, doc_type: DocumentType, channel: MessageChannel
) -> MessageTemplate:
    """M.7.2 rule 6: 'Director-managed library ... per document and
    channel ... only approved [WhatsApp] templates are used for
    business-initiated messages.' Enforced here, not just offered as a
    UI suggestion -- the same server-side-gate discipline this codebase
    applies to every other blueprint rule."""
    template = db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Message template not found")
    if not template.is_active:
        raise HTTPException(status_code=422, detail=f"Template '{template.name}' is not active")
    if template.channel != channel:
        raise HTTPException(
            status_code=422,
            detail=f"Template '{template.name}' is a {template.channel.value} template, not {channel.value}",
        )
    if template.document_type is not None and template.document_type != doc_type:
        raise HTTPException(
            status_code=422,
            detail=f"Template '{template.name}' is for {template.document_type.value}, not {doc_type.value}",
        )
    if channel == MessageChannel.WHATSAPP and template.whatsapp_template_status != WhatsappTemplateStatus.APPROVED:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Template '{template.name}' is not Meta-approved yet "
                f"(status: {template.whatsapp_template_status.value if template.whatsapp_template_status else 'none'})"
            ),
        )
    return template


class MessageCreate(BaseModel):
    doc_type: DocumentType
    doc_id: uuid.UUID
    channel: MessageChannel
    recipient: str = Field(min_length=1)
    template_key: str | None = None
    template_id: uuid.UUID | None = None
    subject: str | None = None
    body_note: str | None = None
    attachment_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    doc_type: DocumentType
    doc_id: uuid.UUID
    channel: MessageChannel
    recipient: str
    sender_id: uuid.UUID
    template_key: str | None
    template_id: uuid.UUID | None
    subject: str | None
    body_note: str | None
    attachment_id: uuid.UUID | None
    status: MessageStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@messages_router.post("", response_model=MessageOut, status_code=201)
def create_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """Part O MESSAGES / M.7.2 rule 1. This is a manual send-tracking
    record, not a real dispatch: no email or WhatsApp provider is wired
    up in this build, so calling this endpoint logs that a PM/Sales/
    Director sent the document themselves (by whatever means) -- it
    never actually sends anything. status is always RECORDED. Repeatable
    any number of times per document (a re-send, a WhatsApp follow-up to
    an earlier email, etc.), independent of the document's own status-
    transition endpoints (POST .../send).

    template_id (M.7.2 rule 6) references a real Director-managed
    MESSAGE_TEMPLATES row -- _resolve_template enforces the channel/
    document-type match and, for WhatsApp, that Meta has actually
    approved it. Its subject/body default subject/body_note when the
    caller doesn't override them; the template's {placeholder} text is
    not substituted (no real provider is wired up to consume the
    rendered result -- see the docstring on MessageTemplate)."""
    _require_doc_type_role(db, payload.doc_type, current_user)
    _get_document_or_404(db, payload.doc_type, payload.doc_id)
    _enforce_client_consent(db, payload.doc_type, payload.doc_id, payload.channel)
    _enforce_internal_document_channel(db, payload.doc_type, payload.channel, payload.recipient)

    if payload.attachment_id is not None:
        attachment = db.query(Attachment).filter(Attachment.id == payload.attachment_id).first()
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        if attachment.doc_type != payload.doc_type or attachment.doc_id != payload.doc_id:
            raise HTTPException(status_code=400, detail="Attachment does not belong to this document")

    subject = payload.subject
    body_note = payload.body_note
    if payload.template_id is not None:
        template = _resolve_template(db, payload.template_id, payload.doc_type, payload.channel)
        if subject is None:
            subject = template.subject
        if body_note is None:
            body_note = template.body[:500]  # body_note is capped at 500 chars, same convention as elsewhere

    message = Message(
        doc_type=payload.doc_type,
        doc_id=payload.doc_id,
        channel=payload.channel,
        recipient=payload.recipient,
        sender_id=current_user.id,
        template_key=payload.template_key,
        template_id=payload.template_id,
        subject=subject,
        body_note=body_note,
        attachment_id=payload.attachment_id,
        status=MessageStatus.RECORDED,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@messages_router.get("", response_model=list[MessageOut])
def list_messages(
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    _require_doc_type_role(db, doc_type, current_user)
    return (
        db.query(Message)
        .filter(Message.doc_type == doc_type, Message.doc_id == doc_id)
        .order_by(Message.created_at.desc())
        .all()
    )
