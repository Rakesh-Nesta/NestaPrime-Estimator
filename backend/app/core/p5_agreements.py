"""P5 contract revision 7, Section 4.1: Agreement lifecycle. Every function here holds the shared lock
order from app.core.p5 (Project -> Quotation -> Agreement -> Authorization -> ... -> Attachment) and
leaves committing to the caller, so each mutation and its audit entry land in one transaction."""

import uuid
from datetime import UTC, date, datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.api.audit_log import write_audit_log_entry
from app.core import p5
from app.models.attachment import Attachment
from app.models.client_signatory import ClientSignatory
from app.models.document import QuotationStatus
from app.models.p5 import Agreement, AgreementStatus
from app.models.project import Project
from app.models.setting import DocumentType
from app.models.user import User
from app.models.work_order import WorkOrder
from sqlalchemy.orm import Session


# The business calendar is India's (Asia/Kolkata, UTC+5:30, no daylight saving): "today" for a signing date is
# the Indian date, never the UTC date (which is a day behind from 00:00 to 05:30 IST) and never the server's
# local date. A fixed offset is exact for IST and needs no tz database.
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "IST")


def _now_utc() -> datetime:
    """Test seam: tests freeze the clock here to probe the midnight-IST boundary."""
    return datetime.now(UTC)


def business_today() -> date:
    return _now_utc().astimezone(BUSINESS_TZ).date()


def _audit(db, actor, agreement, field, old, new, reason, request):
    write_audit_log_entry(db, actor, "agreement", agreement.id, field, old_value=old, new_value=new, reason=reason, request=request)


def evidence_is_intact(db: Session, agreement: Agreement) -> bool | None:
    """None when no evidence is recorded yet; True/False once it is. Defense in depth: the supersede
    guard should make a mismatch impossible, but it is verified independently."""
    if agreement.signed_document_attachment_id is None:
        return None
    attachment = db.get(Attachment, agreement.signed_document_attachment_id)
    return attachment is not None and attachment.original_sha256 == agreement.signed_document_sha256


def _locked_agreement(db: Session, agreement_id) -> tuple[Agreement, p5.LockedScope]:
    probe = db.get(Agreement, agreement_id)
    if probe is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    scope = p5.lock_quotation_scope(db, probe.quotation_id, extra_agreement_ids=[agreement_id])
    agreement = db.execute(
        select(Agreement).where(Agreement.id == agreement_id).execution_options(populate_existing=True)
    ).scalars().first()
    return agreement, scope


def _require_current(agreement: Agreement) -> None:
    if agreement.status in AgreementStatus.NOT_CURRENT:
        raise HTTPException(status_code=409, detail=f"This Agreement revision is no longer current ({agreement.status})")


def create_draft(db: Session, quotation_id, actor: User, request: Request | None) -> Agreement:
    scope = p5.lock_quotation_scope(db, quotation_id)
    quotation = scope.quotation
    if quotation.status != QuotationStatus.WON:
        raise HTTPException(status_code=409, detail="An Agreement can only be drafted once the Quotation is Won")
    if db.execute(select(WorkOrder.id).where(WorkOrder.quotation_id == quotation_id)).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="A Work Order already exists for this quotation; it is adopted as a legacy record by the "
                   "separately authorized backfill, not by drafting a new Agreement",
        )
    if scope.agreement is not None:
        raise HTTPException(
            status_code=409,
            detail=f"This quotation already has a current Agreement ({scope.agreement.status}); "
                   "void or correct it instead of drafting another",
        )
    previous = db.execute(
        select(Agreement)
        .where(Agreement.quotation_id == quotation_id)
        .order_by(Agreement.created_at.desc(), Agreement.id.desc())
    ).scalars().first()
    agreement = Agreement(
        quotation_id=quotation_id,
        project_id=quotation.project_id,
        status=AgreementStatus.DRAFTED,
        # Lineage only: a fresh draft after a withdrawal is NOT a correction of the voided row.
        supersedes_id=previous.id if previous is not None and previous.status == AgreementStatus.VOIDED else None,
        created_by_id=actor.id,
    )
    db.add(agreement)
    db.flush()
    _audit(db, actor, agreement, "status", None, AgreementStatus.DRAFTED, None, request)
    return agreement


def record_client_signature(
    db: Session, agreement_id, signatory_id, signed_on: date, attachment_id, actor: User, request: Request | None
) -> Agreement:
    """drafted -> client_signed. Locks Project -> Quotation -> Agreement, then the Attachment (level 7,
    last). Freezes the signatory snapshot, signing date and the evidence id/hash, and sets
    evidence_locked_at, exactly once."""
    agreement, scope = _locked_agreement(db, agreement_id)
    _require_current(agreement)
    if agreement.status != AgreementStatus.DRAFTED:
        raise HTTPException(status_code=409, detail=f"Only a drafted Agreement can be client-signed (status: {agreement.status})")
    project = scope.project
    if signed_on > business_today():
        raise HTTPException(status_code=422, detail="The signing date cannot be in the future")

    signatory = db.get(ClientSignatory, signatory_id)
    if signatory is None or signatory.client_id != project.client_id:
        raise HTTPException(status_code=422, detail="That signatory does not belong to this project's client")
    if not signatory.is_active:
        raise HTTPException(status_code=422, detail="That signatory is not active")
    if signatory.authorization_date > signed_on or (signatory.expiry_date is not None and signatory.expiry_date < signed_on):
        raise HTTPException(
            status_code=422, detail="The signatory was not authorized on the recorded signing date"
        )

    attachment = p5.lock_attachment(db, attachment_id)
    if attachment is None or attachment.doc_type != DocumentType.AGREEMENT or attachment.doc_id != agreement.id:
        raise HTTPException(status_code=422, detail="The signed document must be an attachment on this Agreement")
    if attachment.superseded_by_id is not None:
        raise HTTPException(status_code=409, detail="That attachment has been superseded; use its latest version")

    now = datetime.now(UTC)
    agreement.client_signatory_id = signatory.id
    agreement.client_signatory_name_snapshot = signatory.name
    agreement.client_signatory_designation_snapshot = signatory.designation
    agreement.client_signed_at = datetime.combine(signed_on, datetime.min.time())
    agreement.signed_document_attachment_id = attachment.id
    agreement.signed_document_sha256 = attachment.original_sha256
    agreement.evidence_locked_at = now
    agreement.status = AgreementStatus.CLIENT_SIGNED
    db.flush()
    _audit(db, actor, agreement, "status", AgreementStatus.DRAFTED, AgreementStatus.CLIENT_SIGNED,
           f"signed by {signatory.name} ({signatory.designation}) on {signed_on}", request)
    return agreement


def execute(db: Session, agreement_id, actor: User, request: Request | None) -> Agreement:
    """client_signed -> executed: the Director's signature for Nesta Prime, frozen at this moment."""
    agreement, _scope = _locked_agreement(db, agreement_id)
    _require_current(agreement)
    if agreement.status != AgreementStatus.CLIENT_SIGNED:
        raise HTTPException(status_code=409, detail=f"Only a client-signed Agreement can be executed (status: {agreement.status})")
    if not evidence_is_intact(db, agreement):
        raise HTTPException(status_code=409, detail="The recorded signed document no longer matches its recorded hash")
    agreement.nesta_signed_by_id = actor.id
    agreement.nesta_signed_at = datetime.now(UTC)
    agreement.status = AgreementStatus.EXECUTED
    db.flush()
    _audit(db, actor, agreement, "status", AgreementStatus.CLIENT_SIGNED, AgreementStatus.EXECUTED,
           f"executed for Nesta Prime by {actor.name}", request)
    return agreement


def void(db: Session, agreement_id, reason: str, actor: User, request: Request | None) -> Agreement:
    agreement, scope = _locked_agreement(db, agreement_id)
    _require_current(agreement)
    if agreement.status == AgreementStatus.LEGACY_ADOPTED:
        raise HTTPException(status_code=409, detail="A legacy-adopted record is not an Agreement and cannot be voided")
    old = agreement.status
    agreement.status = AgreementStatus.VOIDED
    agreement.void_reason = reason
    agreement.voided_at = datetime.now(UTC)
    agreement.voided_by_id = actor.id
    db.flush()
    _audit(db, actor, agreement, "status", old, AgreementStatus.VOIDED, reason, request)
    p5.invalidate_authorization(db, agreement.quotation_id, "Agreement voided", actor, request)
    return agreement


def supersede(db: Session, agreement_id, reason: str, actor: User, request: Request | None) -> Agreement:
    """Correction of a SIGNED Agreement: the old row becomes superseded (history kept, evidence stays
    locked), a new drafted row starts the replacement chain, and any bound authorization is invalidated."""
    agreement, scope = _locked_agreement(db, agreement_id)
    _require_current(agreement)
    if agreement.status not in AgreementStatus.CORRECTABLE:
        raise HTTPException(
            status_code=409,
            detail=f"Only a client-signed or executed Agreement can be corrected (status: {agreement.status})",
        )
    old = agreement.status
    agreement.status = AgreementStatus.SUPERSEDED
    db.flush()
    replacement = Agreement(
        quotation_id=agreement.quotation_id,
        project_id=agreement.project_id,
        status=AgreementStatus.DRAFTED,
        supersedes_id=agreement.id,
        created_by_id=actor.id,
    )
    db.add(replacement)
    db.flush()
    _audit(db, actor, agreement, "status", old, AgreementStatus.SUPERSEDED, reason, request)
    _audit(db, actor, replacement, "status", None, AgreementStatus.DRAFTED, f"correction of {agreement.id}", request)
    p5.invalidate_authorization(db, agreement.quotation_id, "Agreement superseded by a correction", actor, request)
    return replacement


def guard_attachment_supersede(db: Session, attachment: Attachment) -> Attachment:
    """The supersede route's AGREEMENT guard (Section 4.1/4.4). Unlocked read of the attachment is the
    caller's; this acquires Project -> Quotation -> Agreement (the owning one, possibly historical),
    then the Attachment (level 7), re-reads, and refuses if the attachment is -- or became -- locked
    signing evidence or has already been superseded. Returns the re-read, locked attachment."""
    if attachment.doc_type != DocumentType.AGREEMENT:
        return attachment
    probe = db.get(Agreement, attachment.doc_id)
    if probe is not None:
        p5.lock_quotation_scope(db, probe.quotation_id, extra_agreement_ids=[probe.id])
    locked = p5.lock_attachment(db, attachment.id)
    if locked is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if locked.superseded_by_id is not None:
        raise HTTPException(status_code=400, detail="This attachment has already been superseded")
    is_evidence = db.execute(
        select(Agreement.id).where(
            Agreement.signed_document_attachment_id == locked.id, Agreement.evidence_locked_at.isnot(None)
        )
    ).first()
    if is_evidence is not None:
        raise HTTPException(
            status_code=409,
            detail="Signed evidence cannot be superseded directly -- correct the Agreement itself, "
                   "which creates its own new revision",
        )
    return locked
