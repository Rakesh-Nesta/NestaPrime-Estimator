import hashlib
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.documents import _document_no, _rate_blind_mode_on
from app.config import settings
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import ApprovalStrength, Attachment, AttachmentTag
from app.models.client_signatory import ClientSignatory
from app.models.document import CostSheet, CostSheetStatus, Estimate, EstimateOption, EstimateStatus, Quotation
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.price_request import PriceRequest
from app.models.project import Project
from app.models.setting import DocumentType
from app.models.site_survey import SiteSurvey
from app.models.technical_bid_checklist import TechnicalBidChecklistItem
from app.models.user import User, UserRole
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
# A.3: "Site Engineer: Site survey form, actuals entry" / "sees: Survey,
# actuals, drawings" -- the Site Engineer's own attachments (Appendix C's
# "photos (min 4)"), plus PM/Director oversight. No Sales/Procurement row
# in A.3 for this duty.
SITE_SURVEY_ROLES = ("site_engineer", "pm", "director")
# The router-level Depends() below is deliberately a coarse "is this an
# authenticated business role at all" gate covering every role any
# doc_type ever grants access to (everyone except CA/Tax, who has no
# reason to touch any of these document types -- A.3). The real,
# per-doc_type enforcement is _require_doc_type_role()/_roles_for()
# below, called inside each endpoint body -- Sales passing this outer
# gate still gets rejected by that inner check on e.g. a cost_sheet.
ALL_ATTACHMENT_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # M.3: "max 100 MB each"

_DOC_TABLE = {
    DocumentType.COST_SHEET: CostSheet,
    DocumentType.ESTIMATE: Estimate,
    DocumentType.ESTIMATE_OPTION: EstimateOption,
    DocumentType.QUOTATION: Quotation,
    DocumentType.WORK_ORDER: WorkOrder,
    DocumentType.TECHNICAL_BID_CHECKLIST_ITEM: TechnicalBidChecklistItem,
    DocumentType.PRICE_REQUEST: PriceRequest,
    DocumentType.SITE_SURVEY: SiteSurvey,
}

_COST_VISIBILITY_DOC_TYPES = (
    DocumentType.COST_SHEET,
    DocumentType.WORK_ORDER,
    DocumentType.TECHNICAL_BID_CHECKLIST_ITEM,
)


def _roles_for(doc_type: DocumentType) -> tuple[str, ...]:
    if doc_type == DocumentType.PRICE_REQUEST:
        return PRICE_REQUEST_ROLES
    if doc_type == DocumentType.SITE_SURVEY:
        return SITE_SURVEY_ROLES
    return COST_ROLES if doc_type in _COST_VISIBILITY_DOC_TYPES else DOCUMENT_ROLES


def _require_doc_type_role(db: Session, doc_type: DocumentType, current_user) -> None:
    """K.3 Rate-blind mode: 'Sales enters quantities and attaches vendor
    quotes as images.' Files aren't the numeric cost/margin data K.3's
    blanket API-stripping rule is about, so this only widens WHICH
    document types Sales may attach to (Cost Sheet, gated on the mode
    being on) -- it never exposes a rate or amount figure."""
    if doc_type == DocumentType.COST_SHEET and current_user.role.value == "sales":
        if not _rate_blind_mode_on(db):
            raise HTTPException(
                status_code=403, detail="Rate-blind mode is off -- Sales cannot attach files to a Cost Sheet"
            )
        return
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
    # EstimateOption (product images, M.6) has no project_id of its own --
    # only its parent Estimate does. Nothing tags a product_image
    # attachment approval_evidence in practice, but this keeps signatory
    # matching from crashing if it ever is.
    if doc_type == DocumentType.ESTIMATE_OPTION:
        estimate = db.query(Estimate).filter(Estimate.id == document.estimate_id).first()
        project_id = estimate.project_id if estimate else None
    else:
        project_id = document.project_id
    project = db.query(Project).filter(Project.id == project_id).first()
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


def _trigger_structural_design_rebase(
    db: Session, request: Request, current_user, doc_type: DocumentType, doc_id: uuid.UUID, tag: AttachmentTag
) -> None:
    """E.5 'Engineer-override workflow': '(1) the engineer's design is
    uploaded with tag structural_design; (2) the system auto-creates
    CS-R(n+1) in Draft; (3) PM updates member and foundation lines from
    the design; (4) PM re-verifies; (5) linked Estimates/Quotations are
    flagged "rebase required" (M.2 rule 4); (6) Sales is notified.'
    Steps 3/4 stay manual (a human has to actually read the engineer's
    design and re-price it) -- this covers 2, 5 and 6. Step 5 needs no
    code of its own: cost_basis_rebase_required is computed from the
    Cost Sheet's own status (see _cost_sheet_superseded), so superseding
    it here already flags every Estimate/Quotation chained to it.
    Quotations aren't messaged separately since they chain through
    estimate_id, not cost_sheet_id directly -- notifying the Estimate
    covers the whole chain.
    Known gap: 'if the design arrives after the Estimate was Sent, the
    Estimate gets a major revision' -- there is no Estimate-revision
    endpoint in this build (only Cost Sheet has /revise), so a Sent
    Estimate is only flagged and called out in the Sales notification,
    not actually re-revisioned."""
    if tag != AttachmentTag.STRUCTURAL_DESIGN or doc_type != DocumentType.COST_SHEET:
        return
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == doc_id).first()
    if not cost_sheet or cost_sheet.status != CostSheetStatus.VERIFIED:
        return

    project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
    new_revision = CostSheet(
        project_id=cost_sheet.project_id,
        document_no=_document_no(project.project_no, "CS", cost_sheet.revision_major + 1),
        revision_major=cost_sheet.revision_major + 1,
        cost_total=cost_sheet.cost_total,
        created_by_id=current_user.id,
    )
    cost_sheet.status = CostSheetStatus.SUPERSEDED
    db.add(new_revision)
    write_audit_log_entry(
        db, current_user, "cost_sheet", cost_sheet.id, "status",
        old_value=CostSheetStatus.VERIFIED.value, new_value=CostSheetStatus.SUPERSEDED.value,
        reason="Auto-revised: structural engineer design uploaded (E.5 engineer-override workflow)",
        request=request,
    )

    estimates = db.query(Estimate).filter(Estimate.cost_sheet_id == cost_sheet.id).all()
    if estimates:
        sales_emails = [row[0] for row in db.query(User.email).filter(User.role == UserRole.SALES).all()]
        for estimate in estimates:
            body = (
                f"Structural engineer design uploaded for {project.project_no} -- Cost Sheet revised to "
                f"{new_revision.document_no}. Estimate {estimate.document_no} has cost basis changed and "
                "needs to be rebased (M.2 rule 4) before it can be sent."
            )
            if estimate.status == EstimateStatus.SENT:
                body += (
                    " This Estimate was already Sent -- per E.5, it needs a major revision before "
                    "anything further goes to the client."
                )
            for email in sales_emails:
                db.add(
                    Message(
                        doc_type=DocumentType.ESTIMATE,
                        doc_id=estimate.id,
                        channel=MessageChannel.EMAIL,
                        recipient=email,
                        sender_id=current_user.id,
                        template_key="structural_rebase_required",
                        subject="NestaPrime -- structural design uploaded, rebase required",
                        body_note=body[:500],
                        status=MessageStatus.RECORDED,
                    )
                )
    db.commit()


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

    _trigger_structural_design_rebase(db, request, current_user, doc_type, doc_id, tag)
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
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    """M.3: 'Every attachment is stored write-once ... with its SHA-256
    hash, uploader, timestamp and IP.' signatory_name/signatory_designation
    are optional and, when given on an approval_evidence attachment, are
    checked against Part O CLIENT_SIGNATORIES (see _validate_signatory_if_given)."""
    _require_doc_type_role(db, doc_type, current_user)
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
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    _require_doc_type_role(db, doc_type, current_user)
    query = db.query(Attachment).filter(Attachment.doc_type == doc_type, Attachment.doc_id == doc_id)
    if not include_superseded:
        query = query.filter(Attachment.superseded_by_id.is_(None))
    return query.order_by(Attachment.uploaded_at.desc()).all()


@attachments_router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_doc_type_role(db, attachment.doc_type, current_user)

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
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    """M.3: '...no overwrite, no delete -- only supersede.' The old row is
    never mutated; a new row is inserted and the old one's
    superseded_by_id points at it."""
    old = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_doc_type_role(db, old.doc_type, current_user)
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
