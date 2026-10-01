"""P4 contract v7, Section 4: reliable mobile uploads -- the chunked-upload endpoints.

Every one of the four endpoints below independently re-checks BOTH session ownership
(created_by_id must match the caller) AND the target document's current role/ownership access --
including a retry against an already-completed session, which is not exempt either (Section 0
item 2). A session id alone is never sufficient authorization."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict

from sqlalchemy.orm import Session

from app.api.attachments import ALL_ATTACHMENT_ROLES, AttachmentOut, _require_doc_type_role
from app.core import attachment_upload as upload_core
from app.core import ownership
from app.core.auth import require_roles
from app.core.project_stages import advance_stage_on_evidence_upload
from app.db.session import get_db
from app.models.attachment_upload_session import AttachmentUploadSession
from app.models.project_construction_stage import ProjectConstructionStage
from app.models.setting import DocumentType

upload_sessions_router = APIRouter(prefix="/attachments/upload-sessions", tags=["attachment-uploads"])


class StartSessionIn(BaseModel):
    doc_type: DocumentType
    doc_id: uuid.UUID
    filename: str
    declared_size: int
    declared_sha256: str
    chunk_size: int


class SessionOut(BaseModel):
    id: uuid.UUID
    doc_type: str
    doc_id: uuid.UUID
    status: str
    chunk_size: int
    total_chunks: int
    completion_attempt: int
    resulting_attachment_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


def _to_raise(exc: upload_core.UploadProtocolError):
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _authorize_session(db: Session, session: AttachmentUploadSession, current_user) -> None:
    """Session ownership AND the target document's own role/ownership access, together, on every
    call -- a session id alone is never enough (Section 0 item 2)."""
    if session.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="This upload session belongs to a different user")
    doc_type = DocumentType(session.doc_type)
    _require_doc_type_role(db, doc_type, current_user)
    ownership.require_visible_document(db, current_user, doc_type.value, session.doc_id)


def _get_session_or_404(db: Session, session_id: uuid.UUID) -> AttachmentUploadSession:
    session = db.get(AttachmentUploadSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return session


@upload_sessions_router.post("", response_model=SessionOut, status_code=201)
def start_upload_session(
    body: StartSessionIn,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    _require_doc_type_role(db, body.doc_type, current_user)
    ownership.require_visible_document(db, current_user, body.doc_type.value, body.doc_id)
    try:
        session = upload_core.start_session(
            db, current_user, body.doc_type.value, body.doc_id,
            body.filename, body.declared_size, body.declared_sha256, body.chunk_size,
        )
    except upload_core.UploadProtocolError as exc:
        _to_raise(exc)
    return session


@upload_sessions_router.get("/{session_id}", response_model=SessionOut)
def get_upload_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    """Inspect/resume: returns status plus (via a separate detail call, see below) which chunk
    indexes are already written, so a resuming client knows what's left."""
    session = _get_session_or_404(db, session_id)
    _authorize_session(db, session, current_user)
    return session


@upload_sessions_router.get("/{session_id}/status")
def get_upload_session_status(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    session = _get_session_or_404(db, session_id)
    _authorize_session(db, session, current_user)
    return upload_core.session_status(db, session)


@upload_sessions_router.post("/{session_id}/chunks/{chunk_index}")
async def upload_chunk(
    session_id: uuid.UUID,
    chunk_index: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    session = _get_session_or_404(db, session_id)
    _authorize_session(db, session, current_user)
    content = await file.read()
    try:
        claimed_attempt = upload_core.claim_chunk(db, session_id, chunk_index)
        result = upload_core.write_and_promote_chunk(db, session_id, chunk_index, claimed_attempt, content)
    except upload_core.UploadProtocolError as exc:
        _to_raise(exc)
    return result


@upload_sessions_router.post("/{session_id}/complete", response_model=AttachmentOut)
def complete_upload_session(
    session_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    session = _get_session_or_404(db, session_id)
    _authorize_session(db, session, current_user)

    if session.status == "completed":
        # a retry against an already-completed session is not exempt from authorization (checked
        # above) but IS idempotent -- return the same receipt rather than erroring.
        from app.models.attachment import Attachment

        return db.get(Attachment, session.resulting_attachment_id)

    try:
        attempt_token = upload_core.start_completion(db, session_id)
    except upload_core.UploadProtocolError as exc:
        if exc.status_code == 200:
            from app.models.attachment import Attachment

            db.refresh(session)
            return db.get(Attachment, session.resulting_attachment_id)
        _to_raise(exc)

    try:
        assembled_path = upload_core.assemble_and_validate(db, session_id, attempt_token)
        attachment = upload_core.finalize_completion(db, session_id, attempt_token, assembled_path, current_user)
    except upload_core.UploadProtocolError as exc:
        _to_raise(exc)

    if DocumentType(session.doc_type) == DocumentType.PROJECT_STAGE:
        stage = db.query(ProjectConstructionStage).filter(ProjectConstructionStage.id == session.doc_id).first()
        if stage is not None:
            advance_stage_on_evidence_upload(db, stage)
            db.commit()
    return attachment
