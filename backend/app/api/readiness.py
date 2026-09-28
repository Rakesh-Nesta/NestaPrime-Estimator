import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.core.readiness import check_client_identity, compute_waivable_checks
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Estimate, Quotation
from app.models.project import Project
from app.models.readiness_exception import (
    ReadinessCheckKey,
    ReadinessDocumentType,
    ReadinessException,
    ReadinessExceptionStatus,
)

readiness_router = APIRouter(tags=["readiness"])

# WP7 (correction plan, 2026-09-28): "A Director may record an exception directly. A PM
# may only request one" -- Sales is not named for either action here, unlike
# SkipRequest's own REQUEST_ROLES (which does include Sales, per M.4's explicit
# "(requests)" annotation for that different mechanism). A Sales user who hits a blocked,
# waivable check is told, via the readiness payload itself, to ask a PM or Director --
# that is their corrective action, not a request they can log themselves.
REQUEST_ROLES = ("pm", "director")
APPROVE_ROLES = ("director",)
# Read access (the pre-flight checklist) matches who can already reach the Documents
# screen these checks gate -- the same role set send_estimate itself uses.
VIEW_ROLES = ("sales", "pm", "director")


def _document_exists(db: Session, document_type: ReadinessDocumentType, document_id: uuid.UUID) -> bool:
    if document_type == ReadinessDocumentType.ESTIMATE:
        return db.query(Estimate.id).filter(Estimate.id == document_id).first() is not None
    return db.query(Quotation.id).filter(Quotation.id == document_id).first() is not None


class ReadinessExceptionCreate(BaseModel):
    document_type: ReadinessDocumentType
    document_id: uuid.UUID
    check_key: ReadinessCheckKey
    reason: str = Field(min_length=1, max_length=500)


class ReadinessExceptionOut(BaseModel):
    id: uuid.UUID
    document_type: ReadinessDocumentType
    document_id: uuid.UUID
    check_key: ReadinessCheckKey
    reason: str
    status: ReadinessExceptionStatus
    requested_by_id: uuid.UUID
    requested_at: datetime
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None

    model_config = ConfigDict(from_attributes=True)


@readiness_router.post("/readiness-exceptions", response_model=ReadinessExceptionOut, status_code=201)
def create_readiness_exception(
    payload: ReadinessExceptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REQUEST_ROLES)),
):
    """A Director's own call here IS the "record an exception directly" action -- auto-
    approved in the same request, no separate approve call needed. A PM's call creates a
    REQUESTED row that does nothing until a Director approves it (approve_readiness_exception
    below) -- send_estimate/release_quotation only treat APPROVED as satisfying the check."""
    if not _document_exists(db, payload.document_type, payload.document_id):
        raise HTTPException(status_code=404, detail=f"{payload.document_type.value.title()} not found")

    existing = (
        db.query(ReadinessException)
        .filter(
            ReadinessException.document_type == payload.document_type,
            ReadinessException.document_id == payload.document_id,
            ReadinessException.check_key == payload.check_key,
            ReadinessException.status != ReadinessExceptionStatus.REJECTED,
        )
        .first()
    )
    if existing is not None:
        # Idempotent: a repeat request/record for the same still-open check on the same
        # document returns the existing row rather than creating a duplicate.
        return existing

    is_director = current_user.role.value == "director"
    exception = ReadinessException(
        document_type=payload.document_type,
        document_id=payload.document_id,
        check_key=payload.check_key,
        reason=payload.reason,
        requested_by_id=current_user.id,
        status=ReadinessExceptionStatus.APPROVED if is_director else ReadinessExceptionStatus.REQUESTED,
        approved_by_id=current_user.id if is_director else None,
        approved_at=datetime.now(UTC) if is_director else None,
    )
    db.add(exception)
    db.flush()

    write_audit_log_entry(
        db, current_user, payload.document_type.value, payload.document_id, f"readiness_exception:{payload.check_key.value}",
        old_value=None, new_value=exception.status.value, reason=payload.reason, request=request,
    )

    db.commit()
    db.refresh(exception)
    return exception


@readiness_router.get("/readiness-exceptions", response_model=list[ReadinessExceptionOut])
def list_readiness_exceptions(
    document_type: ReadinessDocumentType,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    return (
        db.query(ReadinessException)
        .filter(ReadinessException.document_type == document_type, ReadinessException.document_id == document_id)
        .order_by(ReadinessException.requested_at.desc())
        .all()
    )


@readiness_router.post("/readiness-exceptions/{exception_id}/approve", response_model=ReadinessExceptionOut)
def approve_readiness_exception(
    exception_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*APPROVE_ROLES)),
):
    exception = db.query(ReadinessException).filter(ReadinessException.id == exception_id).first()
    if not exception:
        raise HTTPException(status_code=404, detail="Readiness exception not found")
    if exception.status != ReadinessExceptionStatus.REQUESTED:
        raise HTTPException(status_code=400, detail="This readiness exception has already been decided")

    exception.status = ReadinessExceptionStatus.APPROVED
    exception.approved_by_id = current_user.id
    exception.approved_at = datetime.now(UTC)

    write_audit_log_entry(
        db, current_user, exception.document_type.value, exception.document_id, f"readiness_exception:{exception.check_key.value}",
        old_value=ReadinessExceptionStatus.REQUESTED.value, new_value=ReadinessExceptionStatus.APPROVED.value,
        reason=exception.reason, request=request,
    )

    db.commit()
    db.refresh(exception)
    return exception


class ReadinessExceptionReject(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@readiness_router.post("/readiness-exceptions/{exception_id}/reject", response_model=ReadinessExceptionOut)
def reject_readiness_exception(
    exception_id: uuid.UUID,
    payload: ReadinessExceptionReject,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*APPROVE_ROLES)),
):
    exception = db.query(ReadinessException).filter(ReadinessException.id == exception_id).first()
    if not exception:
        raise HTTPException(status_code=404, detail="Readiness exception not found")
    if exception.status != ReadinessExceptionStatus.REQUESTED:
        raise HTTPException(status_code=400, detail="This readiness exception has already been decided")

    exception.status = ReadinessExceptionStatus.REJECTED
    exception.rejection_reason = payload.reason
    exception.approved_at = None

    write_audit_log_entry(
        db, current_user, exception.document_type.value, exception.document_id, f"readiness_exception:{exception.check_key.value}",
        old_value=ReadinessExceptionStatus.REQUESTED.value, new_value=ReadinessExceptionStatus.REJECTED.value,
        reason=payload.reason, request=request,
    )

    db.commit()
    db.refresh(exception)
    return exception


class ReadinessCheckOut(BaseModel):
    key: str
    label: str
    passed: bool
    waivable: bool
    exception: ReadinessExceptionOut | None = None


class ReadinessOut(BaseModel):
    # The one non-waivable check, reported separately from the waivable list below --
    # there is no exception path for it, so it has no `waivable`/`exception` shape at all.
    client_identity_passed: bool
    client_identity_missing: list[str]
    checks: list[ReadinessCheckOut]


@readiness_router.get("/projects/{project_id}/readiness", response_model=ReadinessOut)
def get_project_readiness(
    project_id: uuid.UUID,
    document_type: ReadinessDocumentType | None = None,
    document_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    """The frontend's own pre-flight panel -- never blocks navigation, just tells the
    caller what send_estimate/release_quotation would currently refuse. Pass no
    document_type/document_id to preview readiness before any Estimate/Quotation exists
    yet (no exception can be shown as waived in that case, since none could exist)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = db.query(Client).filter(Client.id == project.client_id).first()
    identity = check_client_identity(client)

    checks = compute_waivable_checks(db, project, document_type, document_id if document_type else None)
    return ReadinessOut(
        client_identity_passed=identity.passed,
        client_identity_missing=identity.missing,
        checks=[
            ReadinessCheckOut(key=c.key, label=c.label, passed=c.passed, waivable=c.waivable, exception=c.exception)
            for c in checks
        ],
    )
