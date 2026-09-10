import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.message import MessageChannel
from app.models.message_template import MessageTemplate, WhatsappTemplateStatus
from app.models.setting import DocumentType

message_templates_router = APIRouter(prefix="/message-templates", tags=["message-templates"])

# Whoever can send a message (messages.py's own DOCUMENT_ROLES) needs to
# browse the library to pick from it; M.4's own rights table keeps writes
# Director-only ("Manage templates, providers, consent settings" row).
TEMPLATE_READ_ROLES = ("sales", "pm", "director")
TEMPLATE_WRITE_ROLES = ("director",)


class MessageTemplateOut(BaseModel):
    id: uuid.UUID
    document_type: DocumentType | None
    channel: MessageChannel
    name: str
    subject: str | None
    body: str
    whatsapp_template_status: WhatsappTemplateStatus | None
    language: str
    version: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@message_templates_router.get("", response_model=list[MessageTemplateOut])
def list_message_templates(
    channel: MessageChannel | None = None,
    document_type: DocumentType | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*TEMPLATE_READ_ROLES)),
):
    query = db.query(MessageTemplate)
    if channel is not None:
        query = query.filter(MessageTemplate.channel == channel)
    if document_type is not None:
        query = query.filter(MessageTemplate.document_type == document_type)
    if not include_inactive:
        query = query.filter(MessageTemplate.is_active.is_(True))
    return query.order_by(MessageTemplate.channel, MessageTemplate.name).all()


class MessageTemplateCreate(BaseModel):
    document_type: DocumentType | None = None
    channel: MessageChannel
    name: str = Field(min_length=1)
    subject: str | None = None
    body: str = Field(min_length=1)
    language: str = "en"


def _check_duplicate(db: Session, name: str, channel: MessageChannel, exclude_id: uuid.UUID | None = None) -> None:
    query = db.query(MessageTemplate).filter(MessageTemplate.name == name, MessageTemplate.channel == channel)
    if exclude_id is not None:
        query = query.filter(MessageTemplate.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail=f"A {channel.value} template named '{name}' already exists")


@message_templates_router.post("", response_model=MessageTemplateOut, status_code=201)
def create_message_template(
    payload: MessageTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*TEMPLATE_WRITE_ROLES)),
):
    _check_duplicate(db, payload.name, payload.channel)
    template = MessageTemplate(
        document_type=payload.document_type,
        channel=payload.channel,
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
        language=payload.language,
        # M.7.2 rule 6: a WhatsApp template always starts life needing
        # Meta's approval; email has no such gate, so it stays null.
        whatsapp_template_status=(
            WhatsappTemplateStatus.DRAFT if payload.channel == MessageChannel.WHATSAPP else None
        ),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


class MessageTemplateUpdate(BaseModel):
    document_type: DocumentType | None = None
    name: str | None = None
    subject: str | None = None
    body: str | None = None
    language: str | None = None
    whatsapp_template_status: WhatsappTemplateStatus | None = None
    is_active: bool | None = None


@message_templates_router.patch("/{template_id}", response_model=MessageTemplateOut)
def update_message_template(
    template_id: uuid.UUID,
    payload: MessageTemplateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*TEMPLATE_WRITE_ROLES)),
):
    template = db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Message template not found")

    changes = payload.model_dump(exclude_unset=True)
    if "whatsapp_template_status" in changes and template.channel != MessageChannel.WHATSAPP:
        raise HTTPException(status_code=422, detail="whatsapp_template_status only applies to WhatsApp templates")
    if "name" in changes and changes["name"] != template.name:
        _check_duplicate(db, changes["name"], template.channel, exclude_id=template.id)

    content_changed = (
        ("subject" in changes and changes["subject"] != template.subject)
        or ("body" in changes and changes["body"] != template.body)
    )

    for field, value in changes.items():
        setattr(template, field, value)

    if content_changed:
        template.version += 1
        # M.7.2 rule 6: Meta's approval is tied to specific wording -- an
        # edit to a submitted/approved WhatsApp template's content means
        # it needs re-submission, unless this same call also set a new
        # status explicitly (e.g. re-submitting in the same edit).
        if (
            template.channel == MessageChannel.WHATSAPP
            and "whatsapp_template_status" not in changes
            and template.whatsapp_template_status in (WhatsappTemplateStatus.SUBMITTED, WhatsappTemplateStatus.APPROVED)
        ):
            template.whatsapp_template_status = WhatsappTemplateStatus.DRAFT

    db.commit()
    db.refresh(template)
    return template
