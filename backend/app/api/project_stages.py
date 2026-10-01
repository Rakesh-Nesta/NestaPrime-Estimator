"""P4 contract v7, Section 3: stage evidence capture endpoints."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.attachments import STAGE_ROLES
from app.api.audit_log import write_audit_log_entry
from app.core import ownership
from app.core.auth import require_roles
from app.core.project_stages import has_current_evidence
from app.db.session import get_db
from app.models.project import Project
from app.models.project_construction_stage import ProjectConstructionStage, StageStatus

stage_router = APIRouter(tags=["project-stages"])

# P4 contract v7, Section 3/7: "PM and Director may review stages, subject to the same
# document-access check as every other action" -- your own recommendation, adopted here as the
# implementation's default. This was explicitly a recommendation, not your approval, when the
# contract was reviewed; it is implemented as such now that P4 as a whole has been authorized,
# including this default, per your own explicit instruction authorizing this implementation.
REVIEW_ROLES = ("pm", "director")


class StageOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    phase: str
    status: str
    started_at: datetime | None
    evidence_submitted_at: datetime | None
    evidence_submitted_by_id: uuid.UUID | None
    rejection_reason: str | None
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ReviewIn(BaseModel):
    action: str  # "approve" | "reject"
    rejection_reason: str | None = None


def _require_stage_role(current_user) -> None:
    if current_user.role.value not in STAGE_ROLES:
        raise HTTPException(status_code=403, detail=f"Role '{current_user.role.value}' cannot act on stage evidence")


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_stage_or_404(db: Session, stage_id: uuid.UUID) -> ProjectConstructionStage:
    stage = db.query(ProjectConstructionStage).filter(ProjectConstructionStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    return stage


@stage_router.get("/projects/{project_id}/stages", response_model=list[StageOut])
def list_stages(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*STAGE_ROLES)),
):
    _get_project_or_404(db, project_id)
    if ownership.scoping_applies(db, current_user) and not ownership.may_see_project(db, current_user, project_id):
        raise HTTPException(status_code=404, detail=ownership.NOT_FOUND)
    return (
        db.query(ProjectConstructionStage)
        .filter(ProjectConstructionStage.project_id == project_id)
        .order_by(ProjectConstructionStage.phase)
        .all()
    )


@stage_router.post("/stages/{stage_id}/submit", response_model=StageOut)
def submit_stage_for_review(
    stage_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*STAGE_ROLES)),
):
    """P4 contract v7, Section 3: "Mark ready for review" -- Site Engineer, and now PM/Director
    too (revision 4 fix, Section 0.6). Refused server-side if zero current Attachments exist
    against the stage -- there is nothing to review. Available from in_progress (the normal case)
    or rejected (a resubmission that never got re-marked in_progress for some reason -- treated
    the same as in_progress, since evidence already exists either way)."""
    stage = _get_stage_or_404(db, stage_id)
    if ownership.scoping_applies(db, current_user) and not ownership.may_see_project(db, current_user, stage.project_id):
        raise HTTPException(status_code=404, detail=ownership.NOT_FOUND)
    if stage.status not in (StageStatus.IN_PROGRESS.value, StageStatus.REJECTED.value):
        raise HTTPException(
            status_code=400, detail=f"Stage is '{stage.status}' -- only in_progress or rejected stages can be submitted"
        )
    if not has_current_evidence(db, stage.id):
        raise HTTPException(status_code=400, detail="No evidence has been uploaded against this stage yet")

    old_status = stage.status
    stage.status = StageStatus.EVIDENCE_SUBMITTED.value
    stage.evidence_submitted_at = datetime.now(UTC)
    stage.evidence_submitted_by_id = current_user.id
    write_audit_log_entry(
        db, current_user, "project_stage", stage.id, "status",
        old_value=old_status, new_value=stage.status, reason=None, request=request,
    )
    db.commit()
    db.refresh(stage)
    return stage


@stage_router.post("/stages/{stage_id}/review", response_model=StageOut)
def review_stage(
    stage_id: uuid.UUID,
    body: ReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REVIEW_ROLES)),
):
    """P4 contract v7, Section 3: evidence_submitted -> reviewed or -> rejected (a required
    reason), gated to PM/Director, subject to the same document-access check as every other
    action -- role alone is not enough. A rejected stage returns to in_progress only when new
    evidence is next uploaded (advance_stage_on_evidence_upload), never immediately here."""
    stage = _get_stage_or_404(db, stage_id)
    if ownership.scoping_applies(db, current_user) and not ownership.may_see_project(db, current_user, stage.project_id):
        raise HTTPException(status_code=404, detail=ownership.NOT_FOUND)
    if stage.status != StageStatus.EVIDENCE_SUBMITTED.value:
        raise HTTPException(
            status_code=400, detail=f"Stage is '{stage.status}' -- only an evidence_submitted stage can be reviewed"
        )
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'approve' or 'reject'")
    if body.action == "reject" and not body.rejection_reason:
        raise HTTPException(status_code=422, detail="rejection_reason is required to reject a stage")

    old_status = stage.status
    if body.action == "approve":
        stage.status = StageStatus.REVIEWED.value
        stage.rejection_reason = None
    else:
        stage.status = StageStatus.REJECTED.value
        stage.rejection_reason = body.rejection_reason
    stage.reviewed_by_id = current_user.id
    stage.reviewed_at = datetime.now(UTC)
    write_audit_log_entry(
        db, current_user, "project_stage", stage.id, "status",
        old_value=old_status, new_value=stage.status, reason=body.rejection_reason, request=request,
    )
    db.commit()
    db.refresh(stage)
    return stage
