"""P5 contract revision 7: Agreement, project team, execution readiness/authorization, and the
milestone / task / site-issue work items.

Role gates here are NEW routes' own gates; the per-project team restriction for Procurement and Site
Engineer is new, proposed policy (not existing precedent) and applies only to these routes."""

import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core import p5
from app.core import p5_agreements as agreements_core
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import Quotation, QuotationStatus
from app.models.p5 import (
    Agreement,
    MilestoneStatus,
    ProjectExecutionAuthorization,
    ProjectMilestone,
    ProjectSiteIssue,
    ProjectTask,
    ProjectTeamMember,
    SiteIssueStatus,
    TaskStatus,
)
from app.models.project import Project, ProjectPhase
from app.models.user import User
from app.models.work_order import WorkOrder

p5_router = APIRouter(tags=["p5-execution"])

# Reads: Sales is read-only (own-records switch handled by the global enforce_own_records dependency on
# the project_id / quotation_id / ... path parameters); Procurement and Site Engineer need active
# membership of THAT project's team (proposed policy); Admin, CA/Tax and Marketing have no access.
VIEW_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
MANAGE_ROLES = ("pm", "director")
DIRECTOR_ONLY = ("director",)
TASK_UPDATE_ROLES = ("pm", "director", "procurement", "site_engineer")
ISSUE_RAISE_ROLES = ("pm", "director", "site_engineer")


@contextmanager
def _transaction(db: Session):
    """Roll back everything a failed request touched (the shared test session would otherwise keep
    half-applied flushes; in production get_db's close does this)."""
    try:
        yield
    except BaseException:
        db.rollback()
        raise


def _require_team_gate(db: Session, user: User, project_id) -> None:
    if user.role.value in ("procurement", "site_engineer") and p5.is_active_team_member(db, project_id, user.id) is None:
        raise HTTPException(status_code=403, detail="You are not on this project's team")


def _project_or_404(db: Session, project_id) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _require_confirmed(project: Project) -> None:
    if project.phase != ProjectPhase.CONFIRMED:
        raise HTTPException(
            status_code=409, detail="Milestones, tasks and site issues can be created once a quotation is Won"
        )


def _audit(db, actor, entity, entity_id, field, old, new, reason, request):
    write_audit_log_entry(db, actor, entity, entity_id, field, old_value=old, new_value=new, reason=reason, request=request)


# =========================================================================== Agreement


class AgreementOut(BaseModel):
    id: uuid.UUID
    quotation_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    client_signatory_id: uuid.UUID | None
    client_signatory_name_snapshot: str | None
    client_signatory_designation_snapshot: str | None
    client_signed_at: datetime | None
    nesta_signed_by_id: uuid.UUID | None
    nesta_signed_at: datetime | None
    signed_document_attachment_id: uuid.UUID | None
    signed_document_sha256: str | None
    evidence_locked_at: datetime | None
    evidence_intact: bool | None = None
    supersedes_id: uuid.UUID | None
    void_reason: str | None
    voided_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _agreement_out(db: Session, agreement: Agreement) -> AgreementOut:
    out = AgreementOut.model_validate(agreement)
    out.evidence_intact = agreements_core.evidence_is_intact(db, agreement)
    return out


class ClientSignIn(BaseModel):
    client_signatory_id: uuid.UUID
    signed_on: date
    attachment_id: uuid.UUID


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def _quotation_or_404(db: Session, quotation_id) -> Quotation:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation


@p5_router.post("/quotations/{quotation_id}/agreement", response_model=AgreementOut, status_code=201)
def draft_agreement(
    quotation_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    with _transaction(db):
        agreement = agreements_core.create_draft(db, quotation_id, current_user, request)
        db.commit()
    db.refresh(agreement)
    return _agreement_out(db, agreement)


@p5_router.get("/quotations/{quotation_id}/agreement", response_model=AgreementOut)
def get_current_agreement(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    quotation = _quotation_or_404(db, quotation_id)
    _require_team_gate(db, current_user, quotation.project_id)
    agreement = p5.current_agreement(db, quotation_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="No current Agreement for this quotation")
    return _agreement_out(db, agreement)


@p5_router.get("/quotations/{quotation_id}/agreements", response_model=list[AgreementOut])
def list_agreement_revisions(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    quotation = _quotation_or_404(db, quotation_id)
    _require_team_gate(db, current_user, quotation.project_id)
    rows = db.query(Agreement).filter(Agreement.quotation_id == quotation_id).order_by(Agreement.created_at, Agreement.id).all()
    return [_agreement_out(db, a) for a in rows]


@p5_router.get("/agreements/{agreement_id}", response_model=AgreementOut)
def get_agreement(
    agreement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    agreement = db.get(Agreement, agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    _require_team_gate(db, current_user, agreement.project_id)
    return _agreement_out(db, agreement)


@p5_router.post("/agreements/{agreement_id}/client-sign", response_model=AgreementOut)
def client_sign_agreement(
    agreement_id: uuid.UUID,
    body: ClientSignIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    with _transaction(db):
        agreement = agreements_core.record_client_signature(
            db, agreement_id, body.client_signatory_id, body.signed_on, body.attachment_id, current_user, request
        )
        db.commit()
    db.refresh(agreement)
    return _agreement_out(db, agreement)


@p5_router.post("/agreements/{agreement_id}/execute", response_model=AgreementOut)
def execute_agreement(
    agreement_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DIRECTOR_ONLY)),
):
    with _transaction(db):
        agreement = agreements_core.execute(db, agreement_id, current_user, request)
        db.commit()
    db.refresh(agreement)
    return _agreement_out(db, agreement)


@p5_router.post("/agreements/{agreement_id}/void", response_model=AgreementOut)
def void_agreement(
    agreement_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DIRECTOR_ONLY)),
):
    with _transaction(db):
        agreement = agreements_core.void(db, agreement_id, body.reason, current_user, request)
        db.commit()
    db.refresh(agreement)
    return _agreement_out(db, agreement)


@p5_router.post("/agreements/{agreement_id}/supersede", response_model=AgreementOut, status_code=201)
def supersede_agreement(
    agreement_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DIRECTOR_ONLY)),
):
    with _transaction(db):
        replacement = agreements_core.supersede(db, agreement_id, body.reason, current_user, request)
        db.commit()
    db.refresh(replacement)
    return _agreement_out(db, replacement)


# =========================================================================== Execution readiness / authorization


class ReadinessOut(BaseModel):
    quotation_id: uuid.UUID
    agreement_id: uuid.UUID | None
    agreement_status: str | None
    agreement_executed: bool
    eligible_site_engineers: int
    active_delivery_team: bool
    authorization_id: uuid.UUID | None
    authorization_valid: bool
    blockers: list[str]


def _readiness_out(db: Session, quotation: Quotation) -> ReadinessOut:
    report = p5.compute_readiness(db, quotation)
    return ReadinessOut(**report.__dict__)


@p5_router.get("/quotations/{quotation_id}/execution-readiness", response_model=ReadinessOut)
def get_execution_readiness(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    """Read-only: reports live readiness and never changes stored history."""
    return _readiness_out(db, _quotation_or_404(db, quotation_id))


class AuthorizationOut(BaseModel):
    id: uuid.UUID
    quotation_id: uuid.UUID
    agreement_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    authorized_by_id: uuid.UUID
    authorized_at: datetime
    invalidated_at: datetime | None
    invalidated_reason: str | None

    model_config = ConfigDict(from_attributes=True)


@p5_router.post("/quotations/{quotation_id}/execution-authorization", response_model=AuthorizationOut)
def authorize_execution(
    quotation_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    with _transaction(db):
        row, _created = p5.authorize_execution(db, quotation_id, current_user, request)
        db.commit()
    db.refresh(row)
    return row


@p5_router.get("/quotations/{quotation_id}/execution-authorizations", response_model=list[AuthorizationOut])
def list_execution_authorizations(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    _quotation_or_404(db, quotation_id)
    return (
        db.query(ProjectExecutionAuthorization)
        .filter(ProjectExecutionAuthorization.quotation_id == quotation_id)
        .order_by(ProjectExecutionAuthorization.authorized_at, ProjectExecutionAuthorization.id)
        .all()
    )


class ExecutionContextOut(BaseModel):
    """What a project's Execution screen needs to find its way: the Won quotation (id and document number
    only -- no totals) and whether a Work Order exists. Exists because Procurement and Site Engineer team
    members cannot list a project's quotations (documents.py's DOCUMENT_ROLES) yet must reach this screen."""

    project_id: uuid.UUID
    phase: str
    quotation_id: uuid.UUID | None
    quotation_no: str | None
    work_order_exists: bool
    work_order_id: uuid.UUID | None  # PM/Director only, like every other Work Order read
    work_order_status: str | None


@p5_router.get("/projects/{project_id}/execution-context", response_model=ExecutionContextOut)
def get_execution_context(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    project = _project_or_404(db, project_id)
    _require_team_gate(db, current_user, project_id)
    quotation = (
        db.query(Quotation)
        .filter(Quotation.project_id == project_id, Quotation.status == QuotationStatus.WON)
        .order_by(Quotation.created_at.desc(), Quotation.id.desc())
        .first()
    )
    work_order = db.query(WorkOrder).filter(WorkOrder.quotation_id == quotation.id).first() if quotation else None
    manager = current_user.role.value in MANAGE_ROLES
    return ExecutionContextOut(
        project_id=project.id, phase=project.phase.value,
        quotation_id=quotation.id if quotation else None,
        quotation_no=quotation.document_no if quotation else None,
        work_order_exists=work_order is not None,
        work_order_id=work_order.id if (work_order and manager) else None,
        work_order_status=work_order.status.value if (work_order and manager) else None,
    )


# =========================================================================== Team


class TeamMemberOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None = None
    project_role: str
    assigned_by_id: uuid.UUID
    assigned_at: datetime
    removed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


def _member_out(db: Session, member: ProjectTeamMember) -> TeamMemberOut:
    out = TeamMemberOut.model_validate(member)
    user = db.get(User, member.user_id)
    out.user_name = user.name if user else None
    return out


class TeamAssignIn(BaseModel):
    user_id: uuid.UUID
    project_role: str


@p5_router.get("/projects/{project_id}/team", response_model=list[TeamMemberOut])
def list_team(
    project_id: uuid.UUID,
    include_removed: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    _project_or_404(db, project_id)
    _require_team_gate(db, current_user, project_id)
    query = db.query(ProjectTeamMember).filter(ProjectTeamMember.project_id == project_id)
    if not include_removed:
        query = query.filter(ProjectTeamMember.removed_at.is_(None))
    return [_member_out(db, m) for m in query.order_by(ProjectTeamMember.assigned_at, ProjectTeamMember.id).all()]


@p5_router.post("/projects/{project_id}/team", response_model=TeamMemberOut)
def assign_team_member(
    project_id: uuid.UUID,
    body: TeamAssignIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    with _transaction(db):
        member, _created = p5.assign_member(db, project_id, body.user_id, body.project_role, current_user, request)
        db.commit()
    db.refresh(member)
    return _member_out(db, member)


@p5_router.delete("/projects/{project_id}/team/{team_member_id}", response_model=TeamMemberOut)
def remove_team_member(
    project_id: uuid.UUID,
    team_member_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    with _transaction(db):
        member = p5.remove_member(db, project_id, team_member_id, current_user, request)
        db.commit()
    db.refresh(member)
    return _member_out(db, member)


# =========================================================================== Milestones


class MilestoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_date: date | None = None
    work_order_id: uuid.UUID | None = None


class MilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_date: date | None = None
    status: str | None = None


class MilestoneOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    target_date: date | None
    status: str
    work_order_id: uuid.UUID | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _linked_work_order_or_422(db: Session, work_order_id, project_id) -> None:
    if work_order_id is None:
        return
    work_order = db.get(WorkOrder, work_order_id)
    if work_order is None or work_order.project_id != project_id:
        raise HTTPException(status_code=422, detail="That Work Order does not belong to this project")


_MILESTONE_TRANSITIONS = {
    MilestoneStatus.NOT_STARTED: {MilestoneStatus.IN_PROGRESS},
    MilestoneStatus.IN_PROGRESS: {MilestoneStatus.DONE},
    MilestoneStatus.DONE: {MilestoneStatus.IN_PROGRESS},  # reopen: PM/Director (the only roles here)
}


@p5_router.post("/projects/{project_id}/milestones", response_model=MilestoneOut, status_code=201)
def create_milestone(
    project_id: uuid.UUID,
    body: MilestoneIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    project = _project_or_404(db, project_id)
    _require_confirmed(project)
    _linked_work_order_or_422(db, body.work_order_id, project_id)
    milestone = ProjectMilestone(
        project_id=project_id, name=body.name, target_date=body.target_date,
        work_order_id=body.work_order_id, created_by_id=current_user.id,
    )
    with _transaction(db):
        db.add(milestone)
        db.flush()
        _audit(db, current_user, "project_milestone", milestone.id, "created", None, body.name, None, request)
        db.commit()
    db.refresh(milestone)
    return milestone


@p5_router.get("/projects/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    _project_or_404(db, project_id)
    _require_team_gate(db, current_user, project_id)
    return db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project_id).order_by(
        ProjectMilestone.created_at, ProjectMilestone.id
    ).all()


@p5_router.patch("/milestones/{milestone_id}", response_model=MilestoneOut)
def update_milestone(
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    milestone = db.get(ProjectMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    with _transaction(db):
        if body.name is not None:
            milestone.name = body.name
        if "target_date" in body.model_fields_set:
            milestone.target_date = body.target_date
        if body.status is not None and body.status != milestone.status:
            if body.status not in _MILESTONE_TRANSITIONS.get(milestone.status, set()):
                raise HTTPException(status_code=409, detail=f"A milestone cannot go from {milestone.status} to {body.status}")
            _audit(db, current_user, "project_milestone", milestone.id, "status", milestone.status, body.status, None, request)
            milestone.status = body.status
        db.commit()
    db.refresh(milestone)
    return milestone


# =========================================================================== Tasks


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None
    milestone_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None
    milestone_id: uuid.UUID | None = None
    status: str | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    assigned_to_id: uuid.UUID | None
    due_date: date | None
    status: str
    milestone_id: uuid.UUID | None
    needs_reassignment: bool
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _member_on_project_or_422(db: Session, member_id, project_id) -> ProjectTeamMember:
    member = db.get(ProjectTeamMember, member_id)
    if member is None or member.project_id != project_id or member.removed_at is not None:
        raise HTTPException(status_code=422, detail="That team member is not an active member of this project")
    return member


def _milestone_on_project_or_422(db: Session, milestone_id, project_id) -> None:
    if milestone_id is None:
        return
    milestone = db.get(ProjectMilestone, milestone_id)
    if milestone is None or milestone.project_id != project_id:
        raise HTTPException(status_code=422, detail="That milestone does not belong to this project")


_TASK_TRANSITIONS = {
    TaskStatus.NOT_STARTED: {TaskStatus.IN_PROGRESS},
    TaskStatus.IN_PROGRESS: {TaskStatus.DONE},
    TaskStatus.DONE: {TaskStatus.IN_PROGRESS},
}


@p5_router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(
    project_id: uuid.UUID,
    body: TaskIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    project = _project_or_404(db, project_id)
    _require_confirmed(project)
    if body.assigned_to_id is not None:
        _member_on_project_or_422(db, body.assigned_to_id, project_id)
    _milestone_on_project_or_422(db, body.milestone_id, project_id)
    task = ProjectTask(
        project_id=project_id, title=body.title, description=body.description,
        assigned_to_id=body.assigned_to_id, due_date=body.due_date, milestone_id=body.milestone_id,
        created_by_id=current_user.id,
    )
    with _transaction(db):
        db.add(task)
        db.flush()
        _audit(db, current_user, "project_task", task.id, "created", None, body.title, None, request)
        db.commit()
    db.refresh(task)
    return task


@p5_router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
def list_tasks(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    _project_or_404(db, project_id)
    _require_team_gate(db, current_user, project_id)
    return db.query(ProjectTask).filter(ProjectTask.project_id == project_id).order_by(
        ProjectTask.created_at, ProjectTask.id
    ).all()


@p5_router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*TASK_UPDATE_ROLES)),
):
    task = db.get(ProjectTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    is_manager = current_user.role.value in MANAGE_ROLES
    fields = body.model_fields_set
    if not is_manager:
        # Procurement / Site Engineer: only the status of the task CURRENTLY assigned to their own
        # active membership -- never merely because they are on the team, never an unassigned task.
        member = p5.is_active_team_member(db, task.project_id, current_user.id)
        if member is None or task.assigned_to_id != member.id:
            raise HTTPException(status_code=403, detail="Only the task's current assignee can update it")
        if fields - {"status"}:
            raise HTTPException(status_code=403, detail="An assignee can only update the status of their own task")
    with _transaction(db):
        if is_manager:
            if body.title is not None:
                task.title = body.title
            if "description" in fields:
                task.description = body.description
            if "due_date" in fields:
                task.due_date = body.due_date
            if "milestone_id" in fields:
                _milestone_on_project_or_422(db, body.milestone_id, task.project_id)
                task.milestone_id = body.milestone_id
            if "assigned_to_id" in fields:
                if body.assigned_to_id is not None:
                    _member_on_project_or_422(db, body.assigned_to_id, task.project_id)
                _audit(db, current_user, "project_task", task.id, "assigned_to", task.assigned_to_id, body.assigned_to_id, None, request)
                task.assigned_to_id = body.assigned_to_id
                task.needs_reassignment = body.assigned_to_id is None and task.needs_reassignment
        if body.status is not None and body.status != task.status:
            if body.status not in _TASK_TRANSITIONS.get(task.status, set()):
                raise HTTPException(status_code=409, detail=f"A task cannot go from {task.status} to {body.status}")
            _audit(db, current_user, "project_task", task.id, "status", task.status, body.status, None, request)
            task.status = body.status
        db.commit()
    db.refresh(task)
    return task


# =========================================================================== Site issues


class SiteIssueIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    severity: str = Field(default="medium", pattern="^(low|medium|high)$")


class SiteIssueUpdate(BaseModel):
    status: str
    resolution_reason: str | None = Field(default=None, max_length=500)


class SiteIssueOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    severity: str
    status: str
    raised_by_id: uuid.UUID
    resolved_by_id: uuid.UUID | None
    resolution_reason: str | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


_ISSUE_TRANSITIONS = {
    SiteIssueStatus.OPEN: {SiteIssueStatus.IN_REVIEW, SiteIssueStatus.RESOLVED},
    SiteIssueStatus.IN_REVIEW: {SiteIssueStatus.RESOLVED},
    SiteIssueStatus.RESOLVED: set(),
}


@p5_router.post("/projects/{project_id}/site-issues", response_model=SiteIssueOut, status_code=201)
def raise_site_issue(
    project_id: uuid.UUID,
    body: SiteIssueIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ISSUE_RAISE_ROLES)),
):
    project = _project_or_404(db, project_id)
    # Membership-gated reporting for a Site Engineer on these new P5 routes; PM/Director are global.
    # P4's own site-survey / stage-evidence routes keep their existing global-by-role access.
    _require_team_gate(db, current_user, project_id)
    _require_confirmed(project)
    issue = ProjectSiteIssue(
        project_id=project_id, title=body.title, description=body.description,
        severity=body.severity, raised_by_id=current_user.id,
    )
    with _transaction(db):
        db.add(issue)
        db.flush()
        _audit(db, current_user, "project_site_issue", issue.id, "raised", None, body.title, None, request)
        db.commit()
    db.refresh(issue)
    return issue


@p5_router.get("/projects/{project_id}/site-issues", response_model=list[SiteIssueOut])
def list_site_issues(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VIEW_ROLES)),
):
    _project_or_404(db, project_id)
    _require_team_gate(db, current_user, project_id)
    return db.query(ProjectSiteIssue).filter(ProjectSiteIssue.project_id == project_id).order_by(
        ProjectSiteIssue.created_at, ProjectSiteIssue.id
    ).all()


@p5_router.patch("/site-issues/{site_issue_id}", response_model=SiteIssueOut)
def update_site_issue(
    site_issue_id: uuid.UUID,
    body: SiteIssueUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MANAGE_ROLES)),
):
    issue = db.get(ProjectSiteIssue, site_issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Site issue not found")
    if body.status not in _ISSUE_TRANSITIONS.get(issue.status, set()):
        raise HTTPException(status_code=409, detail=f"A site issue cannot go from {issue.status} to {body.status}")
    if body.status == SiteIssueStatus.RESOLVED and not (body.resolution_reason or "").strip():
        raise HTTPException(status_code=422, detail="A resolution reason is required to resolve a site issue")
    with _transaction(db):
        _audit(db, current_user, "project_site_issue", issue.id, "status", issue.status, body.status, body.resolution_reason, request)
        issue.status = body.status
        if body.status == SiteIssueStatus.RESOLVED:
            issue.resolution_reason = body.resolution_reason
            issue.resolved_by_id = current_user.id
            issue.resolved_at = datetime.now(UTC)
        db.commit()
    db.refresh(issue)
    return issue
