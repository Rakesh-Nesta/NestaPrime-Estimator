import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.documents import DOCUMENT_ROLES, _document_no
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheet, CostSheetStatus
from app.models.project import Project
from app.models.skip_request import SkipRequest, SkipRequestStage, SkipRequestStatus

skip_requests_router = APIRouter(tags=["skip-requests"])

# M.4 approval matrix: "Skip a stage / fast-track small job | (requests) |
# check | check |" -- Sales/PM/Director can all REQUEST (M.4's Sales
# column is explicitly annotated "(requests)"), but only PM/Director can
# APPROVE ("Sales cannot skip alone", M.2 rule 3).
REQUEST_ROLES = DOCUMENT_ROLES
APPROVE_ROLES = ("pm", "director")


class SkipRequestCreate(BaseModel):
    stage_skipped: SkipRequestStage
    reason: str = Field(min_length=1, max_length=500)


class SkipRequestOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    stage_skipped: SkipRequestStage
    reason: str
    status: SkipRequestStatus
    requested_by_id: uuid.UUID
    approved_by_id: uuid.UUID | None
    resulting_cost_sheet_id: uuid.UUID | None
    created_at: datetime
    decided_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


@skip_requests_router.post(
    "/projects/{project_id}/skip-requests", response_model=SkipRequestOut, status_code=201
)
def create_skip_request(
    project_id: uuid.UUID,
    payload: SkipRequestCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REQUEST_ROLES)),
):
    """M.2 rule 3: 'Stage omission ... allowed only via Skip-stage request
    -> approved by PM or Director -> reason logged.'"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing_cost_sheet = (
        db.query(CostSheet)
        .filter(CostSheet.project_id == project_id, CostSheet.status != CostSheetStatus.SUPERSEDED)
        .first()
    )
    if existing_cost_sheet:
        raise HTTPException(
            status_code=400,
            detail="An active cost sheet already exists for this project -- nothing to skip",
        )

    pending = (
        db.query(SkipRequest)
        .filter(SkipRequest.project_id == project_id, SkipRequest.status == SkipRequestStatus.PENDING)
        .first()
    )
    if pending:
        raise HTTPException(status_code=400, detail="A skip request is already pending for this project")

    skip_request = SkipRequest(
        project_id=project_id,
        stage_skipped=payload.stage_skipped,
        reason=payload.reason,
        requested_by_id=current_user.id,
    )
    db.add(skip_request)
    db.commit()
    db.refresh(skip_request)
    return skip_request


@skip_requests_router.get("/projects/{project_id}/skip-requests", response_model=list[SkipRequestOut])
def list_skip_requests(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REQUEST_ROLES)),
):
    return (
        db.query(SkipRequest)
        .filter(SkipRequest.project_id == project_id)
        .order_by(SkipRequest.created_at.desc())
        .all()
    )


class SkipRequestApprove(BaseModel):
    # M.2 rule 3 says the skipped Cost Sheet is "auto-generated in
    # background from defaults" but specifies no formula or worked
    # example anywhere -- an explicit, informed decision was made to have
    # the approver enter a ballpark cost_total here (same shape as the
    # existing flat-cost_total Cost Sheet creation path) rather than
    # invent a default-generation algorithm the blueprint doesn't give.
    cost_total: float = Field(gt=0)


@skip_requests_router.post("/skip-requests/{skip_request_id}/approve", response_model=SkipRequestOut)
def approve_skip_request(
    skip_request_id: uuid.UUID,
    payload: SkipRequestApprove,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*APPROVE_ROLES)),
):
    skip_request = db.query(SkipRequest).filter(SkipRequest.id == skip_request_id).first()
    if not skip_request:
        raise HTTPException(status_code=404, detail="Skip request not found")
    if skip_request.status != SkipRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="This skip request has already been decided")

    existing_cost_sheet = (
        db.query(CostSheet)
        .filter(CostSheet.project_id == skip_request.project_id, CostSheet.status != CostSheetStatus.SUPERSEDED)
        .first()
    )
    if existing_cost_sheet:
        raise HTTPException(
            status_code=400,
            detail="An active cost sheet already exists for this project -- nothing to skip",
        )

    project = db.query(Project).filter(Project.id == skip_request.project_id).first()
    cost_sheet = CostSheet(
        project_id=skip_request.project_id,
        document_no=_document_no(project.project_no, "CS", 1),
        cost_total=payload.cost_total,
        status=CostSheetStatus.UNVERIFIED,
        auto_generated=True,
        created_by_id=current_user.id,
    )
    db.add(cost_sheet)
    db.flush()

    skip_request.status = SkipRequestStatus.APPROVED
    skip_request.approved_by_id = current_user.id
    skip_request.resulting_cost_sheet_id = cost_sheet.id
    skip_request.decided_at = datetime.now(UTC)

    # M.5 names "skips" as an audit log category.
    write_audit_log_entry(
        db, current_user, "skip_request", skip_request.id, "status",
        old_value=SkipRequestStatus.PENDING.value, new_value=SkipRequestStatus.APPROVED.value,
        reason=skip_request.reason, request=request,
    )

    db.commit()
    db.refresh(skip_request)
    return skip_request
