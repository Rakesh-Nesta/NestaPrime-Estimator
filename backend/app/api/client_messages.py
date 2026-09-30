import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.attachments import _roles_for
from app.api.clients import READ_ROLES
from app.core import ownership
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Estimate, Quotation
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.project import Project
from app.models.setting import DocumentType
from app.models.site_survey import SiteSurvey

router = APIRouter(prefix="/clients/{client_id}/messages", tags=["client-messages"])

# M.7.1's own table (messages.py's own _CLIENT_FACING_DOC_TYPES): the only doc types that ever
# reach the client. Cost Sheet and everything else internal never appears on Client 360.
_CLIENT_FACING_DOC_TYPES = (DocumentType.ESTIMATE, DocumentType.QUOTATION, DocumentType.SITE_SURVEY)

_DOC_MODEL = {DocumentType.ESTIMATE: Estimate, DocumentType.QUOTATION: Quotation, DocumentType.SITE_SURVEY: SiteSurvey}


class ClientMessageOut(BaseModel):
    id: uuid.UUID
    doc_type: DocumentType
    doc_id: uuid.UUID
    channel: MessageChannel
    recipient: str
    subject: str | None
    body_note: str | None
    status: MessageStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _needs_k3_redaction(db: Session, doc_type: DocumentType, doc_id: uuid.UUID, current_user) -> bool:
    """P2 (Client 360 contract) check 3, independent of checks 1 and 2: does this message's own
    underlying document carry anything K.3 would redact for this viewer? Today the only such
    fact in this codebase is a Quotation's below_floor/cost_basis_unverified flag, stripped from
    a rate-blind Sales user's own QuotationOut elsewhere (documents.py, quotations_admin.py,
    project_overview.py's _quotation_release_label). A message tied to such a Quotation is
    omitted here the same way, rather than shown with its context half-redacted."""
    if doc_type != DocumentType.QUOTATION or current_user.role.value != "sales":
        return False
    quotation = db.query(Quotation).filter(Quotation.id == doc_id).first()
    return bool(quotation and (quotation.below_floor or quotation.cost_basis_unverified))


@router.get("", response_model=list[ClientMessageOut])
def list_client_messages(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """P2 (Client 360 contract) Section 2 Communication tab / Section 7: a message reaches this
    viewer only if it passes all three checks, independently -- (1) the doc_type's own role
    gate, (2) Amendment 60 ownership/scope on the underlying document, (3) K.3 field-level
    redaction. A message failing any one is silently omitted; the response never distinguishes
    why, matching Section 0's disclosure fix ("No messages available to you" covers both "none
    exist" and "some exist but are filtered")."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    out: list[ClientMessageOut] = []
    for doc_type in _CLIENT_FACING_DOC_TYPES:
        if current_user.role.value not in _roles_for(doc_type):
            continue  # check 1
        model = _DOC_MODEL[doc_type]
        documents = (
            db.query(model)
            .join(Project, Project.id == model.project_id)
            .filter(Project.client_id == client_id)
            .all()
        )
        for document in documents:
            # check 2 -- same gating shape as ownership.require_visible_document: only a
            # scoped role with the switch on is restricted to what it owns; matching
            # may_see_document alone (unconditionally) would wrongly hide documents from an
            # unscoped role (PM/Director) or a Sales user with the switch off.
            if ownership.scoping_applies(db, current_user) and not ownership.may_see_document(
                db, current_user, doc_type.value, document.id
            ):
                continue
            if _needs_k3_redaction(db, doc_type, document.id, current_user):
                continue  # check 3
            messages = (
                db.query(Message)
                .filter(Message.doc_type == doc_type, Message.doc_id == document.id)
                .all()
            )
            out.extend(ClientMessageOut.model_validate(m) for m in messages)

    out.sort(key=lambda m: m.created_at, reverse=True)
    return out
