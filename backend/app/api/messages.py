import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.attachments import _get_document_or_404, _require_doc_type_role
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.setting import DocumentType

messages_router = APIRouter(prefix="/messages", tags=["messages"])

# Same role split as attachments.py: Cost Sheet stays cost-gated,
# Estimate/Quotation follow the document-editing roles (M.4).
DOCUMENT_ROLES = ("sales", "pm", "director")


class MessageCreate(BaseModel):
    doc_type: DocumentType
    doc_id: uuid.UUID
    channel: MessageChannel
    recipient: str = Field(min_length=1)
    template_key: str | None = None
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
    transition endpoints (POST .../send)."""
    _require_doc_type_role(payload.doc_type, current_user)
    _get_document_or_404(db, payload.doc_type, payload.doc_id)

    if payload.attachment_id is not None:
        attachment = db.query(Attachment).filter(Attachment.id == payload.attachment_id).first()
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        if attachment.doc_type != payload.doc_type or attachment.doc_id != payload.doc_id:
            raise HTTPException(status_code=400, detail="Attachment does not belong to this document")

    message = Message(
        doc_type=payload.doc_type,
        doc_id=payload.doc_id,
        channel=payload.channel,
        recipient=payload.recipient,
        sender_id=current_user.id,
        template_key=payload.template_key,
        subject=payload.subject,
        body_note=payload.body_note,
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
    _require_doc_type_role(doc_type, current_user)
    return (
        db.query(Message)
        .filter(Message.doc_type == doc_type, Message.doc_id == doc_id)
        .order_by(Message.created_at.desc())
        .all()
    )
