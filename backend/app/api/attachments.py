import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.documents import _document_no, _rate_blind_mode_on
from app.config import settings
from app.core import ownership, upload_policy
from app.core import p5_agreements
from app.core.auth import require_roles
from app.core.project_stages import advance_stage_on_evidence_upload
from app.db.session import get_db
from app.models.attachment import ApprovalStrength, Attachment, AttachmentTag
from app.models.client_signatory import ClientSignatory
from app.models.document import CostSheet, CostSheetStatus, Estimate, EstimateOption, EstimateStatus, Quotation
from app.models.message import Message, MessageChannel, MessageStatus
from app.models.p5 import Agreement, ProjectSiteIssue
from app.models.price_request import PriceRequest
from app.models.project import Project
from app.models.project_construction_stage import ProjectConstructionStage
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
# P4 contract v7, Section 3/7: stage evidence photos follow the same set as Site Survey's own --
# named separately since the two represent different concepts that could diverge later, matching
# this codebase's own convention of naming each gate even where tuples currently coincide.
STAGE_ROLES = ("site_engineer", "pm", "director")
# P5 contract revision 7, Section 4.1: the signed Agreement document can repeat the Quotation's
# commercial terms, so it follows the Quotation's own role tuple rather than the broader attachment
# default (Procurement/Site Engineer team members see Agreement STATUS metadata, never the file).
# Writes (uploading/superseding Agreement files) are narrower still: PM/Director only.
AGREEMENT_ROLES = ("sales", "pm", "director")
AGREEMENT_WRITE_ROLES = ("pm", "director")
SITE_ISSUE_ROLES = ("site_engineer", "pm", "director")
# The router-level Depends() below is deliberately a coarse "is this an
# authenticated business role at all" gate covering every role any
# doc_type ever grants access to (everyone except CA/Tax, who has no
# reason to touch any of these document types -- A.3). The real,
# per-doc_type enforcement is _require_doc_type_role()/_roles_for()
# below, called inside each endpoint body -- Sales passing this outer
# gate still gets rejected by that inner check on e.g. a cost_sheet.
ALL_ATTACHMENT_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
# One upload policy for all three paths lives in app/core/upload_policy.py; these names stay importable from here.
MAX_FILE_SIZE_BYTES = upload_policy.MAX_FILE_SIZE_BYTES  # M.3: "max 100 MB each"
BLOCKED_ATTACHMENT_EXTENSIONS = upload_policy.BLOCKED_ATTACHMENT_EXTENSIONS
MAX_STORED_FILENAME_LENGTH = upload_policy.MAX_STORED_FILENAME_LENGTH
_safe_filename = upload_policy.safe_filename


_DOC_TABLE = {
    DocumentType.COST_SHEET: CostSheet,
    DocumentType.ESTIMATE: Estimate,
    DocumentType.ESTIMATE_OPTION: EstimateOption,
    DocumentType.QUOTATION: Quotation,
    DocumentType.WORK_ORDER: WorkOrder,
    DocumentType.TECHNICAL_BID_CHECKLIST_ITEM: TechnicalBidChecklistItem,
    DocumentType.PRICE_REQUEST: PriceRequest,
    DocumentType.SITE_SURVEY: SiteSurvey,
    DocumentType.PROJECT_STAGE: ProjectConstructionStage,  # P4 contract v7
    DocumentType.AGREEMENT: Agreement,  # P5 contract revision 7
    DocumentType.SITE_ISSUE: ProjectSiteIssue,  # P5 contract revision 7
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
    if doc_type == DocumentType.PROJECT_STAGE:
        return STAGE_ROLES
    if doc_type == DocumentType.AGREEMENT:
        return AGREEMENT_ROLES
    if doc_type == DocumentType.SITE_ISSUE:
        return SITE_ISSUE_ROLES
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


def require_agreement_write(doc_type, current_user) -> None:
    """P5: uploading or superseding a file on an Agreement is a PM/Director action (Sales is read-only)."""
    if doc_type == DocumentType.AGREEMENT and current_user.role.value not in AGREEMENT_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Only a PM or Director can change an Agreement's files")


def require_doc_type_write_access(doc_type: DocumentType, current_user) -> None:
    """Hook for a document type whose WRITE roles are narrower than the roles that may attach to it at all. resumable-upload finalization calls it so a write check made when a session was opened is repeated, on the
    user as they are NOW, when the attachment is committed. (The P5 Agreement rules plug in here: PM/Director only.)"""
    require_agreement_write(doc_type, current_user)  # P5: Agreement files are PM/Director-write only


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

    # P4 contract v7
    captured_at: datetime | None = None
    captured_at_source: str | None = None
    review_status: str | None = None
    reviewed_by_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    marketing_reuse_approved_at: datetime | None = None
    marketing_reuse_approved_by_id: uuid.UUID | None = None
    marketing_reuse_revoked_at: datetime | None = None
    marketing_reuse_revoked_by_id: uuid.UUID | None = None
    derived_from_id: uuid.UUID | None = None

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
        # Amendment 61 (Section 64) item 7: a mobile-only Sales user has no email to notify here.
        sales_emails = [
            row[0]
            for row in db.query(User.email).filter(User.role == UserRole.SALES, User.email.isnot(None)).all()
        ]
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
    # No commit here -- same convention as write_audit_log_entry and _advance_stage_if_applicable;
    # the caller's own single commit covers this function's writes too, in the same transaction.


def _advance_stage_if_applicable(
    db: Session, doc_type: DocumentType, doc_id: uuid.UUID, current_user, request: Request
) -> None:
    """P4 contract v7, Section 3: the not_started/rejected->in_progress and reviewed->
    evidence_submitted transitions are a side effect of a successful upload/supersede against a
    stage -- never of a read, and never for any other doc_type. Does not commit; the caller's own
    db.commit() covers this too, same convention as write_audit_log_entry. A reviewed->
    evidence_submitted invalidation is itself audit-logged here (Section 8 case 9) -- the write
    happens at this layer, not inside advance_stage_on_evidence_upload, since that function lives
    in app/core and current_user/request are only available to its caller here in app/api."""
    if doc_type != DocumentType.PROJECT_STAGE:
        return
    stage = db.query(ProjectConstructionStage).filter(ProjectConstructionStage.id == doc_id).first()
    if stage is None:
        return
    old_status = stage.status
    invalidated_review = advance_stage_on_evidence_upload(db, stage)
    if invalidated_review:
        write_audit_log_entry(
            db, current_user, "project_stage", stage.id, "status",
            old_value=old_status, new_value=stage.status,
            reason="New evidence uploaded after review -- prior sign-off invalidated", request=request,
        )


def _parse_captured_at(raw: str | None) -> datetime | None:
    """P4 contract v7, Section 3: a timezone-less capture timestamp is interpreted as IST
    (Asia/Kolkata) before conversion to UTC for storage -- matching this codebase's own
    established precedent for exactly this problem (WP8's reminder scheduler self-computing
    Asia/Kolkata rather than trusting an ambient timezone). A browser's <input type=datetime-local>
    sends exactly this shape: a plain wall-clock string with no offset."""
    if not raw:
        return None
    from zoneinfo import ZoneInfo

    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return parsed.astimezone(UTC).replace(tzinfo=None)


async def read_bounded(upload: UploadFile, limit: int, status_code: int, detail: str) -> bytes:
    """Read an uploaded file in pieces and stop as soon as it exceeds `limit` -- never trusting a declared size."""
    buffer = bytearray()
    while True:
        piece = await upload.read(upload_policy.READ_PIECE_BYTES)
        if not piece:
            return bytes(buffer)
        buffer.extend(piece)
        if len(buffer) > limit:
            raise HTTPException(status_code=status_code, detail=detail)


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
    captured_at: str | None = None,
    captured_at_source: str | None = None,
) -> Attachment:
    content = await read_bounded(file, MAX_FILE_SIZE_BYTES, 413, "File exceeds the 100 MB limit (M.3)")
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")

    _validate_signatory_if_given(db, doc_type, doc_id, tag, signatory_name, signatory_designation)

    try:
        original_filename = upload_policy.check_filename(file.filename)
    except upload_policy.PolicyViolation as violation:
        raise HTTPException(status_code=violation.status_code, detail=violation.detail)

    sha256 = hashlib.sha256(content).hexdigest()
    dest = _storage_dir(doc_type, doc_id) / f"{uuid.uuid4()}_{original_filename}"
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(content)
    try:
        upload_policy.inspect_file(part, original_filename)  # content signature + optional scanner (quarantines)
        upload_policy.lock_quota(db)  # held until the caller's commit, so the cap below cannot be raced past
        upload_policy.enforce_storage_cap(db, len(content))
    except upload_policy.PolicyViolation as violation:
        part.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(status_code=violation.status_code, detail=violation.detail)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    part.replace(dest)

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
        captured_at=_parse_captured_at(captured_at),
        # Neither column is ever read by any authorization or business-logic decision --
        # display-only, explicitly labelled unverified in the UI regardless of source. A browser
        # upload has no EXIF-reading capability, so an unlabelled capture time defaults to
        # "manual" -- never silently implied to be machine-verified.
        captured_at_source=(captured_at_source or ("manual" if captured_at else None)),
    )
    db.add(attachment)
    db.flush()  # assigns attachment.id within THIS transaction, without ending it -- the caller
    # (upload_attachment / supersede_attachment) does the one commit that covers the Attachment
    # row, _trigger_structural_design_rebase's side effects, and the stage-advance/audit entries
    # together, so a failure partway through never leaves evidence committed with a stale stage
    # or a missing audit entry.
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
    captured_at: str | None = Form(None),
    captured_at_source: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    """M.3: 'Every attachment is stored write-once ... with its SHA-256
    hash, uploader, timestamp and IP.' signatory_name/signatory_designation
    are optional and, when given on an approval_evidence attachment, are
    checked against Part O CLIENT_SIGNATORIES (see _validate_signatory_if_given)."""
    _require_doc_type_role(db, doc_type, current_user)
    require_agreement_write(doc_type, current_user)
    ownership.require_visible_document(db, current_user, doc_type.value, doc_id)  # Amendment 60
    _get_document_or_404(db, doc_type, doc_id)
    attachment = await _store_upload(
        db, request, current_user, doc_type, doc_id, tag, approval_strength, file, version=1,
        signatory_name=signatory_name, signatory_designation=signatory_designation,
        captured_at=captured_at, captured_at_source=captured_at_source,
    )
    _advance_stage_if_applicable(db, doc_type, doc_id, current_user, request)
    db.commit()
    return attachment


@attachments_router.get("", response_model=list[AttachmentOut])
def list_attachments(
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    include_superseded: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    _require_doc_type_role(db, doc_type, current_user)
    ownership.require_visible_document(db, current_user, doc_type.value, doc_id)  # Amendment 60
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
    ownership.require_visible_document(db, current_user, attachment.doc_type, attachment.doc_id)  # Amendment 60

    path = Path(attachment.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored file is missing from disk")
    # The stored bytes are served exactly as uploaded (a signed original is never altered), as a download only,
    # with headers that stop a browser from sniffing or rendering it.
    return FileResponse(
        path, filename=attachment.original_filename,
        media_type=upload_policy.download_media_type(attachment.original_filename),
        headers=upload_policy.download_headers(),
    )


@attachments_router.post("/{attachment_id}/supersede", response_model=AttachmentOut, status_code=201)
async def supersede_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    tag: AttachmentTag | None = Form(None),
    approval_strength: ApprovalStrength | None = Form(None),
    signatory_name: str | None = Form(None),
    signatory_designation: str | None = Form(None),
    captured_at: str | None = Form(None),
    captured_at_source: str | None = Form(None),
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
    ownership.require_visible_document(db, current_user, old.doc_type, old.doc_id)  # Amendment 60
    if old.superseded_by_id is not None:
        raise HTTPException(status_code=400, detail="This attachment has already been superseded")
    require_agreement_write(old.doc_type, current_user)
    # P5 contract revision 7, Section 4.1: refuse to supersede recorded signing evidence, serialized
    # against signature recording under the shared lock order (Agreement lock first, Attachment last).
    old = p5_agreements.guard_attachment_supersede(db, old)

    new = await _store_upload(
        db, request, current_user, old.doc_type, old.doc_id,
        tag or old.tag, approval_strength if approval_strength is not None else old.approval_strength,
        file, version=old.version + 1,
        signatory_name=signatory_name if signatory_name is not None else old.signatory_name,
        signatory_designation=signatory_designation if signatory_designation is not None else old.signatory_designation,
        captured_at=captured_at, captured_at_source=captured_at_source,
    )
    old.superseded_by_id = new.id
    _advance_stage_if_applicable(db, old.doc_type, old.doc_id, current_user, request)
    db.commit()
    return new


# --- P4 contract v7, Section 1: document version history -------------------------------------


@attachments_router.get("/{doc_type}/{doc_id}/lineages", response_model=list[list[AttachmentOut]])
def attachment_lineages(
    doc_type: DocumentType,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    """Stored links run older -> newer (old.superseded_by_id points at its replacement); a
    head's own superseded_by_id is always NULL, so reconstructing history from the current
    version is a reverse lookup, never a forward walk from the head."""
    _require_doc_type_role(db, doc_type, current_user)
    ownership.require_visible_document(db, current_user, doc_type.value, doc_id)  # Amendment 60
    rows = (
        db.query(Attachment)
        .filter(Attachment.doc_type == doc_type, Attachment.doc_id == doc_id)
        .order_by(Attachment.version)
        .all()
    )
    predecessor_of = {row.superseded_by_id: row for row in rows if row.superseded_by_id is not None}
    heads = [row for row in rows if row.superseded_by_id is None]

    lineages = []
    for head in heads:
        chain = [head]
        current = head
        while current.id in predecessor_of:
            current = predecessor_of[current.id]
            chain.append(current)
        lineages.append(list(reversed(chain)))  # oldest-first, ending at head
    return lineages


# --- P4 contract v7, Section 2: search across attachments -------------------------------------


class AttachmentSearchResultOut(BaseModel):
    total: int
    items: list[AttachmentOut]


@attachments_router.get("/search", response_model=AttachmentSearchResultOut)
def search_attachments_endpoint(
    q: str | None = None,
    doc_type: DocumentType | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ATTACHMENT_ROLES)),
):
    """Current-version-only (superseded rows never surface here). No autocomplete/suggestion
    endpoint exists, deliberately -- the exact "hidden filenames leak via suggestions" risk this
    contract closed by never creating that surface at all."""
    from app.core.attachment_search import search_attachments

    limit = max(1, min(limit, 100))
    result = search_attachments(db, current_user, q, doc_type, limit, offset)
    return result


# --- P4 contract v7, Section 5: review and marketing-reuse approval ---------------------------


class ReviewIn(BaseModel):
    status: str  # "approved" | "rejected"


@attachments_router.post("/{attachment_id}/review", response_model=AttachmentOut)
def review_attachment(
    attachment_id: uuid.UUID,
    body: ReviewIn,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("pm", "director")),
):
    """Repeatable, not one-way: a PM/Director may re-review an attachment at any time -- this
    simply overwrites review_status/reviewed_by_id/reviewed_at again. Requires the same
    document-access check as every other action, not the role gate in isolation."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ownership.require_visible_document(db, current_user, attachment.doc_type.value, attachment.doc_id)
    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="status must be 'approved' or 'rejected'")
    attachment.review_status = body.status
    attachment.reviewed_by_id = current_user.id
    attachment.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(attachment)
    return attachment


@attachments_router.post("/{attachment_id}/marketing-reuse/approve", response_model=AttachmentOut)
def approve_marketing_reuse(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("pm", "director")),
):
    """Repeatable: a fresh approval after a revocation overwrites approved_at/_by_id and clears
    the revoked pair, since it supersedes the old revocation -- the full approve/revoke/approve
    history lives in the audit log, never reconstructable from these columns alone."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ownership.require_visible_document(db, current_user, attachment.doc_type.value, attachment.doc_id)
    if attachment.doc_type == DocumentType.AGREEMENT:
        raise HTTPException(status_code=409, detail="A signed Agreement is not marketing material")
    attachment.marketing_reuse_approved_at = datetime.now(UTC)
    attachment.marketing_reuse_approved_by_id = current_user.id
    attachment.marketing_reuse_revoked_at = None
    attachment.marketing_reuse_revoked_by_id = None
    db.commit()
    db.refresh(attachment)
    return attachment


@attachments_router.post("/{attachment_id}/marketing-reuse/revoke", response_model=AttachmentOut)
def revoke_marketing_reuse(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("pm", "director")),
):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ownership.require_visible_document(db, current_user, attachment.doc_type.value, attachment.doc_id)
    if attachment.marketing_reuse_approved_at is None:
        raise HTTPException(status_code=400, detail="This attachment has no active marketing-reuse approval to revoke")
    attachment.marketing_reuse_revoked_at = datetime.now(UTC)
    attachment.marketing_reuse_revoked_by_id = current_user.id
    db.commit()
    db.refresh(attachment)
    return attachment
