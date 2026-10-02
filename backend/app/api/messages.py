import base64
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.attachments import _get_document_or_404, _require_doc_type_role, _resolve_client_id
from app.core import ownership
from app.api.pdf_documents import build_estimate_pdf, build_quotation_pdf
from app.api.settings import get_internal_email_domains
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.client import Client
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.message_template import MessageTemplate, WhatsappTemplateStatus
from app.models.setting import DocumentType
from app.services import ai_content, email_gateway, telegram, wa_gateway
from app.services.message_rendering import render_placeholders

logger = logging.getLogger(__name__)

messages_router = APIRouter(prefix="/messages", tags=["messages"])

# Amendment 8 (Section 8): the two doc types that actually have a
# generated PDF today (build_estimate_pdf/build_quotation_pdf) -- the
# only ones include_document=True can attach.
_DOC_TYPES_WITH_PDF = (DocumentType.ESTIMATE, DocumentType.QUOTATION)

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
    consent -- there is no opt-in that makes it acceptable to WhatsApp
    (or, by the same reasoning, Telegram -- Amendment 8's Section 8 spec
    keeps Cost Sheet client-external channels off the table entirely) a
    Cost Sheet or email it outside the company."""
    if doc_type not in _INTERNAL_DOC_TYPES:
        return
    if channel in (MessageChannel.WHATSAPP, MessageChannel.TELEGRAM):
        raise HTTPException(
            status_code=400,
            detail=f"Internal documents (Cost Sheet) may never be sent by {channel.value} (M.7.2 rule 7)",
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
    if channel == MessageChannel.TELEGRAM and not client.telegram_opt_in:
        raise HTTPException(
            status_code=400,
            detail=f"Client '{client.name}' has not opted in to Telegram messages (M.7.2 rule 5)",
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
    # Amendment 8 (Section 8), Section 17: attach the document's own
    # generated PDF (Estimate/Quotation only -- no PDF exists for any
    # other doc_type). Works the same for WhatsApp, Telegram, and email
    # alike; irrelevant if attachment_id is also given (an explicit
    # stored file always wins over the generated one).
    include_document: bool = False
    # A stable id for THIS send. The screen creates one when the dialog opens and reuses it for every retry of the same
    # send: a retry returns the existing outcome and never sends again; the same id with different content is refused.
    # Optional so older callers keep working (the server then generates one and no retry protection applies to them).
    request_id: uuid.UUID | None = None


# --- send-attempt outcomes -------------------------------------------------------------------------------------------
# pending   -- recorded, provider not yet answered (or the process died before it could be recorded)
# accepted  -- the provider accepted it. This is NOT a delivery or read receipt: the recipient may not have it.
# failed    -- confirmed NOT sent (refused before anything went out: not configured, connection refused, a definite rejection)
# unknown   -- may or may not have been sent (timeout/dropped connection after the request left, a 5xx reply, or a pending
#              attempt that was never finalized)
# recorded  -- legacy manual log entry (no send was attempted by this app)
PENDING_STALE_AFTER = timedelta(seconds=120)
DUPLICATE_WARNING = "The previous message may already have been sent. Sending again could create a duplicate."
OUTCOME_LABELS = {
    "pending": "Sending…",
    "accepted": "Accepted by provider—delivery unconfirmed",
    "failed": "Not sent — the provider refused it",
    "unknown": "Outcome unknown — the message may or may not have been sent",
    "recorded": "Logged — no send was attempted",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def effective_attempt_state(message: Message) -> str:
    state = message.attempt_state
    if state is None:  # legacy row: derive from the coarse status
        if message.status in (MessageStatus.SENT, MessageStatus.DELIVERED):
            return "accepted"
        return "failed" if message.status == MessageStatus.FAILED else "recorded"
    if state == "pending" and _utcnow() - (message.attempt_state_at or message.created_at) > PENDING_STALE_AFTER:
        return "unknown"  # a pending attempt that never finished is never silently treated as "not sent"
    return state


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
    provider_message_id: str | None
    created_at: datetime
    request_id: str | None = None
    include_document: bool = False
    attempt_state: str | None = "recorded"
    outcome_label: str = ""
    previous_attempt_id: uuid.UUID | None = None
    resend_confirmed_at: datetime | None = None
    resend_requires_confirmation: bool = False  # True unless the outcome is a CONFIRMED failure
    already_recorded: bool = False  # True when this response is the existing outcome of a retried request id

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_message(cls, message: Message, already_recorded: bool = False) -> "MessageOut":
        state = effective_attempt_state(message)
        out = cls.model_validate(message)
        out.attempt_state = state
        out.outcome_label = OUTCOME_LABELS[state]
        out.resend_requires_confirmation = state != "failed"
        out.already_recorded = already_recorded
        return out


def _document_for_send(
    doc_type: DocumentType, doc_id: uuid.UUID, db: Session, current_user
) -> tuple[bytes, str] | None:
    """Generates the Estimate/Quotation PDF fresh (never stored) for a
    real WhatsApp/Telegram send. Returns (bytes, filename) or None if
    this doc_type has no PDF."""
    if doc_type == DocumentType.ESTIMATE:
        buffer, filename = build_estimate_pdf(db, doc_id)
        return buffer.getvalue(), filename
    if doc_type == DocumentType.QUOTATION:
        buffer, filename = build_quotation_pdf(db, doc_id, current_user)
        return buffer.getvalue(), filename
    return None


def _dispatch_send(
    message: Message, outbound_text: str, doc_bytes: bytes | None, doc_filename: str | None,
) -> None:
    """Amendment 8 (Section 8): the one real send attempt this endpoint makes -- synchronous, matching this app's style
    everywhere else. Mutates the message's status / attempt_state / provider id in place; never raises for a provider
    failure. The OUTCOME is classified truthfully: a failure before anything went out is a confirmed `failed`; a failure
    after the request may have left (timeout, dropped connection, 5xx) is `unknown`, not `failed`; provider acceptance is
    `accepted` (never "delivered")."""
    try:
        if message.channel == MessageChannel.WHATSAPP:
            if doc_bytes:
                provider_id = wa_gateway.send_media(
                    message.recipient, "document", base64.b64encode(doc_bytes).decode(),
                    doc_filename, "application/pdf", caption=outbound_text or None,
                )
            else:
                provider_id = wa_gateway.send_text(message.recipient, outbound_text)
        elif message.channel == MessageChannel.TELEGRAM:
            if doc_bytes:
                provider_id = telegram.send_document(
                    message.recipient, doc_bytes, doc_filename, caption=outbound_text or None
                )
            else:
                provider_id = telegram.send_text(message.recipient, outbound_text)
        else:
            # Section 17 (Amendment 8 continuation): real SMTP send. Subject falls back to the document reference.
            subject = message.subject or f"{message.doc_type.value.replace('_', ' ').title()} document"
            email_gateway.send_email(
                message.recipient, subject, outbound_text,
                attachment_bytes=doc_bytes, attachment_filename=doc_filename,
            )
            provider_id = None
    except (wa_gateway.WaGatewayError, telegram.TelegramError, email_gateway.EmailGatewayError) as exc:
        logger.warning("Message send failed (channel=%s, ambiguous=%s): %s", message.channel.value, exc.ambiguous, exc)
        if exc.ambiguous:
            message.status = MessageStatus.RECORDED  # not confirmed either way
            message.attempt_state = "unknown"
        else:
            message.status = MessageStatus.FAILED
            message.attempt_state = "failed"
        message.attempt_state_at = _utcnow()
        return
    message.status = MessageStatus.SENT
    message.attempt_state = "accepted"
    message.attempt_state_at = _utcnow()
    message.provider_message_id = provider_id


class MessageDraftRequest(BaseModel):
    doc_type: DocumentType
    doc_id: uuid.UUID
    channel: MessageChannel


class MessageDraftOut(BaseModel):
    draft: str


@messages_router.post("/draft", response_model=MessageDraftOut)
def draft_message(
    payload: MessageDraftRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """Amendment 13 (Section 12): returns a suggested message -- never
    saved, never sent, by this endpoint. Pre-fills the existing note
    field; the person still reviews/edits it and clicks the existing
    Send button themselves, same review-then-send shape the note field
    already had before this amendment. M.7.2 consent/internal-document
    gates aren't checked here -- drafting text never reaches the client,
    only a real POST /messages send does, and those gates still apply
    there unchanged."""
    _require_doc_type_role(db, payload.doc_type, current_user)
    ownership.require_visible_document(db, current_user, payload.doc_type.value, payload.doc_id)  # Amendment 60
    document = _get_document_or_404(db, payload.doc_type, payload.doc_id)
    client_id = _resolve_client_id(db, payload.doc_type, payload.doc_id)
    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None

    details = [f"Document: {payload.doc_type.value} {getattr(document, 'document_no', '')}".strip()]
    if client is not None:
        details.append(f"Client: {client.name}")
    if payload.doc_type == DocumentType.QUOTATION and getattr(document, "quotation_total", None) is not None:
        details.append(f"Amount (incl. GST): Rs {float(document.quotation_total):,.0f}")
    expires_at = getattr(document, "expires_at", None)
    if expires_at is not None:
        details.append(f"Valid until: {expires_at.date().isoformat()}")

    tone = "short and casual-professional, suitable for WhatsApp/Telegram" if payload.channel in (
        MessageChannel.WHATSAPP, MessageChannel.TELEGRAM
    ) else "professional, suitable for email"
    prompt = (
        f"Write a brief client-facing message ({tone}) to accompany the document below. "
        "No greeting placeholder, no sign-off, no subject line -- just the message body, plain text, "
        "2-4 sentences.\n\n" + "\n".join(details)
    )
    try:
        draft = ai_content.generate_text(prompt)
    except ai_content.AiContentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return MessageDraftOut(draft=draft)


def _fingerprint(payload: MessageCreate, document, subject: str | None, body_note: str | None) -> str:
    """Hash of the INTENDED content: what, to whom, by which channel, and the version of the document it refers to. Used to
    refuse a reused request id that carries different content. (The bytes actually sent are recorded separately.)"""
    version = [getattr(document, "document_no", None), str(getattr(document, "status", None)), str(getattr(document, "updated_at", None))]
    material = [
        payload.doc_type.value, str(payload.doc_id), payload.channel.value, payload.recipient.strip().lower(),
        str(payload.template_id), subject, body_note, str(payload.attachment_id), bool(payload.include_document), version,
    ]
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()


def _replay_or_refuse(existing: Message, current_user, fingerprint: str) -> Message:
    """The request id was already used. Same sender + same content => return the EXISTING outcome (no new send);
    anything else is refused, so an id can never be used to smuggle different content through."""
    if existing.sender_id != current_user.id or existing.request_fingerprint != fingerprint:
        raise HTTPException(status_code=409, detail={
            "code": "request_id_reused",
            "message": "This request id was already used for a different message. Start a new send instead.",
        })
    return existing


def _perform_send(
    payload: MessageCreate, db: Session, current_user, request: Request | None, response: Response | None,
    previous: Message | None = None, confirmed_by: tuple | None = None,
) -> MessageOut:
    _require_doc_type_role(db, payload.doc_type, current_user)
    ownership.require_visible_document(db, current_user, payload.doc_type.value, payload.doc_id)  # Amendment 60
    document = _get_document_or_404(db, payload.doc_type, payload.doc_id)
    _enforce_client_consent(db, payload.doc_type, payload.doc_id, payload.channel)
    _enforce_internal_document_channel(db, payload.doc_type, payload.channel, payload.recipient)

    if payload.include_document and payload.doc_type not in _DOC_TYPES_WITH_PDF:
        raise HTTPException(
            status_code=422,
            detail=f"{payload.doc_type.value} has no generated document to attach",
        )

    attachment = None
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

    request_id = str(payload.request_id) if payload.request_id else str(uuid.uuid4())
    fingerprint = _fingerprint(payload, document, subject, body_note)
    existing = db.query(Message).filter(Message.request_id == request_id).first()
    if existing is not None:  # an ordinary retry: return the recorded outcome, send nothing
        existing = _replay_or_refuse(existing, current_user, fingerprint)
        if response is not None:
            response.status_code = 200
        return MessageOut.from_message(existing, already_recorded=True)

    # --- everything that can refuse or fail BEFORE the provider is contacted happens here, so a refusal (consent, an
    # excluded PDF image, a busy PDF service ...) never leaves an attempt behind.
    client_id = _resolve_client_id(db, payload.doc_type, payload.doc_id)
    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
    default_text = f"Please find attached: {getattr(document, 'document_no', payload.doc_type.value)}"
    outbound_text = render_placeholders(body_note or default_text, payload.doc_type, document, client)
    doc_bytes: bytes | None = None
    doc_filename: str | None = None
    if attachment is not None:
        path = Path(attachment.storage_path)
        if path.exists():
            doc_bytes = path.read_bytes()
            doc_filename = attachment.original_filename
    elif payload.include_document:
        doc_bytes, doc_filename = _document_for_send(payload.doc_type, payload.doc_id, db, current_user)

    # --- RECORD THE ATTEMPT FIRST (committed), then contact the provider. A crash after transmission leaves this row
    # `pending`, which is reported as `unknown` once stale and blocks a blind duplicate.
    message = Message(
        doc_type=payload.doc_type, doc_id=payload.doc_id, channel=payload.channel, recipient=payload.recipient,
        sender_id=current_user.id, template_key=payload.template_key, template_id=payload.template_id, subject=subject,
        body_note=body_note, attachment_id=payload.attachment_id, status=MessageStatus.RECORDED,
        request_id=request_id, request_fingerprint=fingerprint, include_document=bool(payload.include_document),
        content_sha256=hashlib.sha256(doc_bytes).hexdigest() if doc_bytes else None,
        attempt_state="pending", attempt_state_at=_utcnow(),
        previous_attempt_id=previous.id if previous is not None else None,
    )
    db.add(message)
    if confirmed_by is not None:
        message.resend_confirmed_by_id, message.resend_confirmed_at = confirmed_by[0].id, _utcnow()
        db.flush()
        write_audit_log_entry(
            db, current_user, "message", message.id, "resend_confirmed", effective_attempt_state(previous), "confirmed",
            reason=DUPLICATE_WARNING, request=request,
        )
    try:
        db.commit()
    except IntegrityError:  # another request with the same id won the race: return ITS outcome
        db.rollback()
        winner = db.query(Message).filter(Message.request_id == request_id).first()
        if winner is None:
            raise
        winner = _replay_or_refuse(winner, current_user, fingerprint)
        if response is not None:
            response.status_code = 200
        return MessageOut.from_message(winner, already_recorded=True)

    try:
        _dispatch_send(message, outbound_text, doc_bytes, doc_filename)
    except Exception:  # noqa: BLE001 - an unexpected error AFTER the attempt was recorded must not look like "not sent"
        logger.exception("Unexpected error while sending message %s", message.id)
        message.attempt_state = "unknown"
        message.attempt_state_at = _utcnow()
    db.commit()
    db.refresh(message)
    return MessageOut.from_message(message)


@messages_router.post("", response_model=MessageOut, status_code=201)
def create_message(
    payload: MessageCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """Part O MESSAGES / M.7.2 rule 1: 'Every send creates a MESSAGES record.' The attempt is recorded BEFORE the provider is
    contacted (request id, intended recipient and content fingerprint committed first), so a crash after transmission leaves a
    recoverable `pending`/`unknown` attempt instead of permitting an unnoticed duplicate. An ordinary retry reuses the same
    request_id and gets the existing outcome back with status 200 -- it never sends again; reusing the id with different
    content is refused (409). Provider acceptance is reported as 'Accepted by provider -- delivery unconfirmed'.

    template_id (M.7.2 rule 6) references a real Director-managed MESSAGE_TEMPLATES row; its subject/body default the
    message's subject/body_note when the caller doesn't override them. The stored body_note keeps the literal {placeholder}
    template text unchanged; only the text actually handed to a provider is rendered."""
    return _perform_send(payload, db, current_user, request, response)


class ResendIn(BaseModel):
    request_id: uuid.UUID | None = None
    confirm_duplicate_risk: bool = False


@messages_router.post("/{message_id}/resend", response_model=MessageOut, status_code=201)
def resend_message(
    message_id: uuid.UUID,
    payload: ResendIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """"Send again anyway": creates a NEW attempt linked to the earlier one. Unless the earlier attempt is a CONFIRMED
    failure, the caller must explicitly confirm the duplicate risk (confirm_duplicate_risk=true); the confirmation is
    recorded on the new row and in the audit log. Calling it again with the same request_id returns the same new attempt
    (no third send)."""
    original = db.query(Message).filter(Message.id == message_id).first()
    if original is None:
        raise HTTPException(status_code=404, detail="Message not found")
    _require_doc_type_role(db, original.doc_type, current_user)
    ownership.require_visible_document(db, current_user, original.doc_type.value, original.doc_id)  # Amendment 60

    if payload.request_id is not None:  # an ordinary retry of THIS resend: return it, whatever the original's state is now
        again = db.query(Message).filter(Message.request_id == str(payload.request_id)).first()
        if again is not None:
            if again.sender_id != current_user.id or again.previous_attempt_id != original.id:
                raise HTTPException(status_code=409, detail={
                    "code": "request_id_reused",
                    "message": "This request id was already used for a different message. Start a new send instead.",
                })
            response.status_code = 200
            return MessageOut.from_message(again, already_recorded=True)

    state = effective_attempt_state(original)
    # every state except a CONFIRMED failure (including a legacy manual log entry) needs the explicit confirmation below
    confirmed_by = None
    if state != "failed":
        if not payload.confirm_duplicate_risk:
            raise HTTPException(status_code=409, detail={
                "code": "duplicate_risk_confirmation_required",
                "message": DUPLICATE_WARNING,
                "previous_outcome": state,
                "previous_outcome_label": OUTCOME_LABELS[state],
            })
        confirmed_by = (current_user,)
    new_payload = MessageCreate(
        doc_type=original.doc_type, doc_id=original.doc_id, channel=original.channel, recipient=original.recipient,
        template_key=original.template_key, template_id=original.template_id, subject=original.subject,
        body_note=original.body_note, attachment_id=original.attachment_id, include_document=original.include_document,
        request_id=payload.request_id or uuid.uuid4(),
    )
    return _perform_send(new_payload, db, current_user, request, response, previous=original, confirmed_by=confirmed_by)


@messages_router.get("", response_model=list[MessageOut])
def list_messages(
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    _require_doc_type_role(db, doc_type, current_user)
    ownership.require_visible_document(db, current_user, doc_type.value, doc_id)  # Amendment 60
    rows = (
        db.query(Message)
        .filter(Message.doc_type == doc_type, Message.doc_id == doc_id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return [MessageOut.from_message(row) for row in rows]
