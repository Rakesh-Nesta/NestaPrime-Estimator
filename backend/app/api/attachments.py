import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import ApprovalStrength, Attachment, AttachmentTag
from app.models.document import CostSheet, Estimate, Quotation
from app.models.setting import DocumentType

attachments_router = APIRouter(prefix="/attachments", tags=["attachments"])

# M.3's stages: Cost Sheet stays behind the same cost-visibility gate as
# every other cost-sheet endpoint; Estimate/Quotation attachments follow
# the document-editing roles (M.4's own "create cost sheet / estimate /
# quotation" row).
COST_ROLES = ("pm", "director")
DOCUMENT_ROLES = ("sales", "pm", "director")
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # M.3: "max 100 MB each"

_DOC_TABLE = {
    DocumentType.COST_SHEET: CostSheet,
    DocumentType.ESTIMATE: Estimate,
    DocumentType.QUOTATION: Quotation,
}


def _roles_for(doc_type: DocumentType) -> tuple[str, ...]:
    return COST_ROLES if doc_type == DocumentType.COST_SHEET else DOCUMENT_ROLES


def _require_doc_type_role(doc_type: DocumentType, current_user) -> None:
    if current_user.role.value not in _roles_for(doc_type):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role.value}' cannot manage attachments on a {doc_type.value}",
        )


def _get_document_or_404(db: Session, doc_type: DocumentType, doc_id: uuid.UUID):
    model = _DOC_TABLE[doc_type]
    document = db.query(model).filter(model.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail=f"{doc_type.value} not found")
    return document


def _storage_dir(doc_type: DocumentType, doc_id: uuid.UUID) -> Path:
    path = Path(settings.attachment_storage_root) / doc_type.value / str(doc_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


class AttachmentOut(BaseModel):
    id: uuid.UUID
    doc_type: DocumentType
    doc_id: uuid.UUID
    original_filename: str
    original_size: int
    original_sha256: str
    tag: AttachmentTag
    approval_strength: ApprovalStrength | None
    uploaded_by_id: uuid.UUID
    uploaded_at: datetime
    version: int
    superseded_by_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


async def _store_upload(
    db: Session,
    request: Request,
    current_user,
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    tag: AttachmentTag,
    approval_strength: ApprovalStrength | None,
    file: UploadFile,
    version: int,
) -> Attachment:
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 100 MB limit (M.3)")
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")

    sha256 = hashlib.sha256(content).hexdigest()
    original_filename = file.filename or "upload"
    dest = _storage_dir(doc_type, doc_id) / f"{uuid.uuid4()}_{original_filename}"
    dest.write_bytes(content)

    attachment = Attachment(
        doc_type=doc_type,
        doc_id=doc_id,
        original_filename=original_filename,
        original_size=len(content),
        original_sha256=sha256,
        storage_path=str(dest),
        tag=tag,
        approval_strength=approval_strength,
        uploaded_by_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        version=version,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@attachments_router.post("", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    request: Request,
    doc_type: DocumentType = Form(...),
    doc_id: uuid.UUID = Form(...),
    tag: AttachmentTag = Form(...),
    approval_strength: ApprovalStrength | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.3: 'Every attachment is stored write-once ... with its SHA-256
    hash, uploader, timestamp and IP.'"""
    _require_doc_type_role(doc_type, current_user)
    _get_document_or_404(db, doc_type, doc_id)
    return await _store_upload(db, request, current_user, doc_type, doc_id, tag, approval_strength, file, version=1)


@attachments_router.get("", response_model=list[AttachmentOut])
def list_attachments(
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    include_superseded: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    _require_doc_type_role(doc_type, current_user)
    query = db.query(Attachment).filter(Attachment.doc_type == doc_type, Attachment.doc_id == doc_id)
    if not include_superseded:
        query = query.filter(Attachment.superseded_by_id.is_(None))
    return query.order_by(Attachment.uploaded_at.desc()).all()


@attachments_router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_doc_type_role(attachment.doc_type, current_user)

    path = Path(attachment.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored file is missing from disk")
    return FileResponse(path, filename=attachment.original_filename)


@attachments_router.post("/{attachment_id}/supersede", response_model=AttachmentOut, status_code=201)
async def supersede_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    tag: AttachmentTag | None = Form(None),
    approval_strength: ApprovalStrength | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.3: '...no overwrite, no delete -- only supersede.' The old row is
    never mutated; a new row is inserted and the old one's
    superseded_by_id points at it."""
    old = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_doc_type_role(old.doc_type, current_user)
    if old.superseded_by_id is not None:
        raise HTTPException(status_code=400, detail="This attachment has already been superseded")

    new = await _store_upload(
        db, request, current_user, old.doc_type, old.doc_id,
        tag or old.tag, approval_strength if approval_strength is not None else old.approval_strength,
        file, version=old.version + 1,
    )
    old.superseded_by_id = new.id
    db.commit()
    return new
