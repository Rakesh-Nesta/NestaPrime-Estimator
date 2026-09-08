import hashlib
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import ApprovalStrength, Attachment, AttachmentTag
from app.models.client_signatory import ClientSignatory
from app.models.document import CostSheet, Estimate, Quotation
from app.models.price_request import PriceRequest
from app.models.project import Project
from app.models.setting import DocumentType
from app.models.technical_bid_checklist import TechnicalBidChecklistItem
from app.models.work_order import WorkOrder

attachments_router = APIRouter(prefix="/attachments", tags=["attachments"])

# M.3's stages: Cost Sheet stays behind the same cost-visibility gate as
# every other cost-sheet endpoint; Estimate/Quotation attachments follow
# the document-editing roles (M.4's own "create cost sheet / estimate /
# quotation" row). Work Order and the technical bid checklist follow
# Part L / M.1 stage 4's own PM/Director-only access -- no Sales row.
COST_ROLES = ("pm", "director")
DOCUMENT_ROLES = ("sales", "pm", "director")
# M.7.5: "Send RFQ / PO / price-update request to vendor" and "Confirm a
# vendor reply as a rate proposal" are both Procurement/PM/Director, not
# Sales -- Price Request attachments (a vendor's quotation PDF/photo,
# tagged vendor_quote) follow that same set rather than either fixed
# tuple above.
PRICE_REQUEST_ROLES = ("pm", "director", "procurement")
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # M.3: "max 100 MB each"

_DOC_TABLE = {
    DocumentType.COST_SHEET: CostSheet,
    DocumentType.ESTIMATE: Estimate,
    DocumentType.QUOTATION: Quotation,
    DocumentType.WORK_ORDER: WorkOrder,
    DocumentType.TECHNICAL_BID_CHECKLIST_ITEM: TechnicalBidChecklistItem,
    DocumentType.PRICE_REQUEST: PriceRequest,
}

_COST_VISIBILITY_DOC_TYPES = (
    DocumentType.COST_SHEET,
    DocumentType.WORK_ORDER,
    DocumentType.TECHNICAL_BID_CHECKLIST_ITEM,
)


def _roles_for(doc_type: DocumentType) -> tuple[str, ...]:
    if doc_type == DocumentType.PRICE_REQUEST:
        return PRICE_REQUEST_ROLES
    return COST_ROLES if doc_type in _COST_VISIBILITY_DOC_TYPES else DOCUMENT_ROLES


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


def _resolve_client_id(db: Session, doc_type: DocumentType, doc_id: uuid.UUID) -> uuid.UUID | None:
    document = _get_document_or_404(db, doc_type, doc_id)
    project = db.query(Project).filter(Project.id == document.project_id).first()
    return project.client_id if project else None


def _match_active_signatory(db: Session, client_id: uuid.UUID, name: str, designation: str) -> bool:
    """Part O CLIENT_SIGNATORIES / M.3: 'name + designation match an
    active record whose authorization_date <= approval date and
    expiry_date is null or later.'"""
    today = date.today()
    return (
        db.query(ClientSignatory)
        .filter(
            ClientSignatory.client_id == client_id,
            ClientSignatory.is_active.is_(True),
            ClientSignatory.name.ilike(name.strip()),
            ClientSignatory.designation.ilike(designation.strip()),
            ClientSignatory.authorization_date <= today,
        )
        .filter((ClientSignatory.expiry_date.is_(None)) | (ClientSignatory.expiry_date >= today))
        .first()
        is not None
    )


def _validate_signatory_if_given(
    db: Session,
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    tag: AttachmentTag,
    signatory_name: str | None,
    signatory_designation: str | None,
) -> None:
    """Signatory matching only ever applies to approval_evidence
    attachments, and only when the uploader chooses to name one --
    leaving both fields blank keeps today's behaviour (an
    approval_evidence attachment with no recorded approver is still
    valid evidence). Naming only one of the two is treated as a mistake,
    not a partial match, since the blueprint's rule is a name+designation
    pair."""
    if not signatory_name and not signatory_designation:
        return
    if tag != AttachmentTag.APPROVAL_EVIDENCE:
        raise HTTPException(
            status_code=422, detail="signatory_name/signatory_designation only apply to approval_evidence attachments"
        )
    if not signatory_name or not signatory_designation:
        raise HTTPException(status_code=422, detail="Both signatory_name and signatory_designation are required together")

    client_id = _resolve_client_id(db, doc_type, doc_id)
    if not client_id or not _match_active_signatory(db, client_id, signatory_name, signatory_designation):
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{signatory_name}' ({signatory_designation}) does not match an active, "
                "in-date client signatory (Part O CLIENT_SIGNATORIES)"
            ),
        )


class AttachmentOut(BaseModel):
    id: uuid.UUID
    doc_type: DocumentType
    doc_id: uuid.UUID
    original_filename: str
    original_size: int
    original_sha256: str
    tag: AttachmentTag
    approval_strength: ApprovalStrength | None
    signatory_name: str | None
    signatory_designation: str | None
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
    signatory_name: str | None = None,
    signatory_designation: str | None = None,
) -> Attachment:
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 100 MB limit (M.3)")
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")

    _validate_signatory_if_given(db, doc_type, doc_id, tag, signatory_name, signatory_designation)

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
        signatory_name=signatory_name,
        signatory_designation=signatory_designation,
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
    signatory_name: str | None = Form(None),
    signatory_designation: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.3: 'Every attachment is stored write-once ... with its SHA-256
    hash, uploader, timestamp and IP.' signatory_name/signatory_designation
    are optional and, when given on an approval_evidence attachment, are
    checked against Part O CLIENT_SIGNATORIES (see _validate_signatory_if_given)."""
    _require_doc_type_role(doc_type, current_user)
    _get_document_or_404(db, doc_type, doc_id)
    return await _store_upload(
        db, request, current_user, doc_type, doc_id, tag, approval_strength, file, version=1,
        signatory_name=signatory_name, signatory_designation=signatory_designation,
    )


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
    signatory_name: str | None = Form(None),
    signatory_designation: str | None = Form(None),
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
        signatory_name=signatory_name if signatory_name is not None else old.signatory_name,
        signatory_designation=signatory_designation if signatory_designation is not None else old.signatory_designation,
    )
    old.superseded_by_id = new.id
    db.commit()
    return new
