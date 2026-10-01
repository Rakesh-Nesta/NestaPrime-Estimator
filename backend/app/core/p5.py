"""P5 contract revision 7: the single place that owns P5's lock order, live readiness checks, the one
authorization-invalidation writer, team assignment/removal, and the account-change protocol.

ONE TOTAL LOCK ORDER (Section 4.4), acquired level by level, every row of a level in ascending id before
the next level begins; each path takes only the levels it needs and never goes back:

    1 Project   2 Quotation   3 Agreement   4 ProjectExecutionAuthorization
    5 ProjectTeamMember   6 User   7 Attachment

All locks are SELECT ... FOR UPDATE with populate_existing, so a row re-read after acquiring its lock
reflects whatever committed while this transaction waited (READ COMMITTED).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.models.attachment import Attachment
from app.models.document import Quotation, QuotationStatus
from app.models.p5 import (
    Agreement,
    AgreementStatus,
    AuthorizationStatus,
    ProjectExecutionAuthorization,
    ProjectTask,
    ProjectTeamMember,
    TaskStatus,
)
from app.models.project import Project
from app.models.user import User, UserRole

RETRY_LIMIT = 3
ASSIGNABLE_PROJECT_ROLES = ("pm", "director", "site_engineer", "procurement")
REQUIRED_DELIVERY_ROLE = "site_engineer"

# Test seam for the account-change retry protocol: called between unlocked discovery and revalidation.
_after_discovery_hook = None


# --------------------------------------------------------------------------- locks


def _uuids(ids) -> list:
    """Normalize to UUID objects so str and UUID ids can never be mixed in one sort (the sort IS the
    lock order's 'ascending id' rule)."""
    return sorted({i if isinstance(i, uuid.UUID) else uuid.UUID(str(i)) for i in ids if i is not None})


def _lock_rows(db: Session, model, ids) -> list:
    ids = _uuids(ids)
    if not ids:
        return []
    stmt = (
        select(model)
        .where(model.id.in_(ids))
        .order_by(model.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(db.execute(stmt).scalars().all())


def lock_projects(db: Session, ids) -> list[Project]:
    return _lock_rows(db, Project, ids)


def lock_quotations(db: Session, ids) -> list[Quotation]:
    return _lock_rows(db, Quotation, ids)


def lock_agreements(db: Session, ids) -> list[Agreement]:
    return _lock_rows(db, Agreement, ids)


def lock_users(db: Session, ids) -> list[User]:
    return _lock_rows(db, User, ids)


def lock_attachment(db: Session, attachment_id) -> Attachment | None:
    rows = _lock_rows(db, Attachment, [attachment_id])
    return rows[0] if rows else None


def lock_authorizations(db: Session, quotation_ids) -> list[ProjectExecutionAuthorization]:
    qids = _uuids(quotation_ids)
    if not qids:
        return []
    stmt = (
        select(ProjectExecutionAuthorization)
        .where(
            ProjectExecutionAuthorization.quotation_id.in_(qids),
            ProjectExecutionAuthorization.status == AuthorizationStatus.AUTHORIZED,
        )
        .order_by(ProjectExecutionAuthorization.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(db.execute(stmt).scalars().all())


def lock_active_team(db: Session, project_ids) -> list[ProjectTeamMember]:
    pids = _uuids(project_ids)
    if not pids:
        return []
    stmt = (
        select(ProjectTeamMember)
        .where(ProjectTeamMember.project_id.in_(pids), ProjectTeamMember.removed_at.is_(None))
        .order_by(ProjectTeamMember.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(db.execute(stmt).scalars().all())


def current_agreement(db: Session, quotation_id) -> Agreement | None:
    stmt = (
        select(Agreement)
        .where(Agreement.quotation_id == quotation_id, Agreement.status.notin_(AgreementStatus.NOT_CURRENT))
        .execution_options(populate_existing=True)
    )
    return db.execute(stmt).scalars().first()


@dataclass
class LockedScope:
    project: Project
    quotation: Quotation | None
    agreement: Agreement | None
    authorizations: list = field(default_factory=list)
    team: list = field(default_factory=list)


def lock_quotation_scope(
    db: Session,
    quotation_id,
    *,
    extra_agreement_ids=(),
    with_team: bool = False,
    extra_user_ids=(),
) -> LockedScope:
    """Levels 1-4 for one quotation (and 5-6 when with_team: the eligibility read). An unlocked read of
    the quotation finds its project; everything is then re-read under the locks."""
    quotation_id = quotation_id if isinstance(quotation_id, uuid.UUID) else uuid.UUID(str(quotation_id))
    probe = db.get(Quotation, quotation_id)
    if probe is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    projects = lock_projects(db, [probe.project_id])
    quotations = lock_quotations(db, [quotation_id])
    current = current_agreement(db, quotation_id)
    agreement_ids = {a for a in extra_agreement_ids} | ({current.id} if current else set())
    lock_agreements(db, agreement_ids)
    auths = lock_authorizations(db, [quotation_id])
    team = []
    if with_team:
        team = lock_active_team(db, [probe.project_id])
        user_ids = {m.user_id for m in team if m.project_role == REQUIRED_DELIVERY_ROLE} | set(extra_user_ids)
        lock_users(db, user_ids)
    current = current_agreement(db, quotation_id)
    return LockedScope(projects[0], quotations[0] if quotations else None, current, auths, team)


def lock_project_scope(db: Session, project_ids, *, user_ids=()) -> None:
    """Levels 1-6 for a project-scoped mutation (team assignment/removal, account change): Projects, then
    the Quotations/Agreements/Authorizations reachable from those projects' valid authorizations, then
    TeamMember rows, then User rows (the changing/assigned users plus every relied-upon engineer)."""
    pids = _uuids(project_ids)
    lock_projects(db, pids)
    if pids:
        rows = db.execute(
            select(ProjectExecutionAuthorization.quotation_id, ProjectExecutionAuthorization.agreement_id)
            .where(
                ProjectExecutionAuthorization.project_id.in_(pids),
                ProjectExecutionAuthorization.status == AuthorizationStatus.AUTHORIZED,
            )
        ).all()
    else:
        rows = []
    qids = {r[0] for r in rows}
    lock_quotations(db, qids)
    lock_agreements(db, {r[1] for r in rows})
    lock_authorizations(db, qids)
    team = lock_active_team(db, pids)
    relied = {m.user_id for m in team if m.project_role == REQUIRED_DELIVERY_ROLE}
    lock_users(db, relied | set(user_ids))


# --------------------------------------------------------------------------- readiness


def eligible_site_engineers(db: Session, project_id) -> list[User]:
    """An active membership labelled site_engineer whose user is active AND really holds the
    site_engineer login role right now (Section 4.2). Always read fresh."""
    stmt = (
        select(User)
        .join(ProjectTeamMember, ProjectTeamMember.user_id == User.id)
        .where(
            ProjectTeamMember.project_id == project_id,
            ProjectTeamMember.removed_at.is_(None),
            ProjectTeamMember.project_role == REQUIRED_DELIVERY_ROLE,
            User.is_active.is_(True),
            User.role == UserRole.SITE_ENGINEER,
        )
        .execution_options(populate_existing=True)
    )
    return list(db.execute(stmt).scalars().all())


def valid_authorization(db: Session, quotation_id) -> ProjectExecutionAuthorization | None:
    return (
        db.execute(
            select(ProjectExecutionAuthorization)
            .where(
                ProjectExecutionAuthorization.quotation_id == quotation_id,
                ProjectExecutionAuthorization.status == AuthorizationStatus.AUTHORIZED,
            )
            .execution_options(populate_existing=True)
        )
        .scalars()
        .first()
    )


@dataclass
class ReadinessReport:
    quotation_id: uuid.UUID
    agreement_id: uuid.UUID | None
    agreement_status: str | None
    agreement_executed: bool
    eligible_site_engineers: int
    active_delivery_team: bool
    authorization_id: uuid.UUID | None
    authorization_valid: bool
    blockers: list[str]


def compute_readiness(db: Session, quotation: Quotation) -> ReadinessReport:
    """Read-only: recomputes every time, writes nothing, never caches (a GET must not change history)."""
    agreement = current_agreement(db, quotation.id)
    executed = agreement is not None and agreement.status == AgreementStatus.EXECUTED
    engineers = eligible_site_engineers(db, quotation.project_id)
    team_ok = len(engineers) >= 1
    auth = valid_authorization(db, quotation.id)
    auth_valid = bool(auth and agreement is not None and executed and team_ok and auth.agreement_id == agreement.id)
    blockers = []
    if agreement is None:
        blockers.append("No Agreement exists for this quotation")
    elif not executed:
        blockers.append(f"The Agreement is not executed (status: {agreement.status})")
    if not team_ok:
        blockers.append("No active, eligible Site Engineer is assigned to this project's team")
    if executed and team_ok and not auth_valid:
        blockers.append("Execution has not been authorized for the current Agreement")
    return ReadinessReport(
        quotation.id, agreement.id if agreement else None, agreement.status if agreement else None,
        executed, len(engineers), team_ok, auth.id if auth else None, auth_valid, blockers,
    )


# --------------------------------------------------------------------------- the one invalidation writer


def invalidate_authorization(
    db: Session, quotation_id, reason: str, actor: User, request: Request | None
) -> ProjectExecutionAuthorization | None:
    """The ONLY code allowed to move an authorization authorized -> invalidated. Caller holds the
    shared locks and commits; the audit entry rides the same transaction."""
    row = valid_authorization(db, quotation_id)
    if row is None:
        return None
    row.status = AuthorizationStatus.INVALIDATED
    row.invalidated_at = datetime.now(UTC)
    row.invalidated_reason = reason[:300]
    db.flush()
    write_audit_log_entry(
        db, actor, "execution_authorization", row.id, "status",
        old_value=AuthorizationStatus.AUTHORIZED, new_value=AuthorizationStatus.INVALIDATED,
        reason=reason, request=request,
    )
    return row


def invalidate_if_no_eligible_engineer(
    db: Session, project_ids, reason: str, actor: User, request: Request | None
) -> list[uuid.UUID]:
    """Recompute under the caller's locks (pending changes flushed first) and invalidate every valid
    authorization of a project that no longer has an eligible Site Engineer."""
    db.flush()
    invalidated = []
    for pid in sorted({p for p in project_ids if p is not None}):
        if eligible_site_engineers(db, pid):
            continue
        rows = db.execute(
            select(ProjectExecutionAuthorization.quotation_id).where(
                ProjectExecutionAuthorization.project_id == pid,
                ProjectExecutionAuthorization.status == AuthorizationStatus.AUTHORIZED,
            )
        ).all()
        for (qid,) in rows:
            if invalidate_authorization(db, qid, reason, actor, request) is not None:
                invalidated.append(qid)
    return invalidated


# --------------------------------------------------------------------------- authorize


def authorize_execution(db: Session, quotation_id, actor: User, request: Request | None):
    """Returns (authorization, created). Idempotent: a still-valid authorization for the current
    executed Agreement is returned unchanged."""
    scope = lock_quotation_scope(db, quotation_id, with_team=True)
    quotation = scope.quotation
    if quotation is None or quotation.status != QuotationStatus.WON:
        raise HTTPException(status_code=409, detail="Execution can only be authorized for a Won quotation")
    report = compute_readiness(db, quotation)
    if not report.agreement_executed:
        raise HTTPException(status_code=409, detail="Execution cannot be authorized: " + report.blockers[0])
    if not report.active_delivery_team:
        raise HTTPException(
            status_code=409, detail="Execution cannot be authorized: no active, eligible Site Engineer on the team"
        )
    existing = valid_authorization(db, quotation_id)
    if existing is not None and existing.agreement_id == scope.agreement.id:
        return existing, False
    if existing is not None:
        invalidate_authorization(db, quotation_id, "Replaced: bound Agreement is no longer current", actor, request)
    row = ProjectExecutionAuthorization(
        quotation_id=quotation_id,
        agreement_id=scope.agreement.id,
        project_id=quotation.project_id,
        authorized_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    write_audit_log_entry(
        db, actor, "execution_authorization", row.id, "status",
        old_value=None, new_value=AuthorizationStatus.AUTHORIZED,
        reason=f"quotation {quotation_id}, agreement {scope.agreement.id}", request=request,
    )
    return row, True


def require_work_order_authorization(db: Session, quotation: Quotation, scope: LockedScope) -> None:
    """Called inside create_work_order's own locked transaction -- the live recheck, never a cached read."""
    report = compute_readiness(db, quotation)
    if not report.agreement_executed:
        raise HTTPException(status_code=409, detail="A Work Order needs an executed Agreement: " + report.blockers[0])
    if not report.active_delivery_team:
        raise HTTPException(
            status_code=409, detail="A Work Order needs at least one active, eligible Site Engineer on the project team"
        )
    if not report.authorization_valid:
        raise HTTPException(
            status_code=409,
            detail="A Work Order needs a current execution authorization for this quotation's executed Agreement",
        )


# --------------------------------------------------------------------------- team


def _audit(db, actor, entity, entity_id, field_name, old, new, reason, request):
    write_audit_log_entry(db, actor, entity, entity_id, field_name, old_value=old, new_value=new, reason=reason, request=request)


def assign_member(db: Session, project_id, user_id, project_role: str, actor: User, request: Request | None):
    """Returns (membership, created). Takes levels 1-6, locking the assignee's User row and rechecking
    active status and role under that lock -- this recheck gates ASSIGNMENT only."""
    if project_role not in ASSIGNABLE_PROJECT_ROLES:
        raise HTTPException(status_code=422, detail=f"project_role must be one of {', '.join(ASSIGNABLE_PROJECT_ROLES)}")
    lock_project_scope(db, [project_id], user_ids=[user_id])
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    user = db.execute(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    ).scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=422, detail="Choose an active user to assign")
    if user.role.value != project_role:
        raise HTTPException(
            status_code=422,
            detail=f"The user's login role ({user.role.value}) does not match the project role ({project_role})",
        )
    existing = db.execute(
        select(ProjectTeamMember)
        .where(
            ProjectTeamMember.project_id == project_id,
            ProjectTeamMember.user_id == user_id,
            ProjectTeamMember.removed_at.is_(None),
        )
        .execution_options(populate_existing=True)
    ).scalars().first()
    if existing is not None:
        return existing, False
    member = ProjectTeamMember(
        project_id=project_id, user_id=user_id, project_role=project_role, assigned_by_id=actor.id
    )
    db.add(member)
    db.flush()
    _audit(db, actor, "project_team_member", member.id, "assigned", None, f"{user.name} as {project_role}", None, request)
    return member, True


def remove_member(db: Session, project_id, member_id, actor: User, request: Request | None) -> ProjectTeamMember:
    """Never gated on the removed member's current eligibility: removing an inactive or role-changed
    member is always permitted. Open tasks are un-assigned and flagged; authorizations that lose their
    last eligible Site Engineer are invalidated -- all in this one transaction."""
    lock_project_scope(db, [project_id])
    member = db.execute(
        select(ProjectTeamMember)
        .where(ProjectTeamMember.id == member_id, ProjectTeamMember.project_id == project_id)
        .execution_options(populate_existing=True)
    ).scalars().first()
    if member is None:
        raise HTTPException(status_code=404, detail="Team member not found")
    if member.removed_at is not None:
        raise HTTPException(status_code=409, detail="This team member was already removed")
    member.removed_at = datetime.now(UTC)
    member.removed_by_id = actor.id
    db.flush()
    open_tasks = db.execute(
        select(ProjectTask).where(ProjectTask.assigned_to_id == member.id, ProjectTask.status != TaskStatus.DONE)
        .order_by(ProjectTask.id)
    ).scalars().all()
    for task in open_tasks:
        task.assigned_to_id = None
        task.needs_reassignment = True
        _audit(db, actor, "project_task", task.id, "assigned_to", member.id, None,
               "Team member removed -- task needs reassignment", request)
    _audit(db, actor, "project_team_member", member.id, "removed", member.project_role, None, None, request)
    invalidate_if_no_eligible_engineer(
        db, [project_id], "Last eligible Site Engineer removed from the team", actor, request
    )
    return member


# --------------------------------------------------------------------------- account changes


def _discover_site_engineer_projects(db: Session, user_id) -> set:
    rows = db.execute(
        select(ProjectTeamMember.project_id)
        .where(
            ProjectTeamMember.user_id == user_id,
            ProjectTeamMember.removed_at.is_(None),
            ProjectTeamMember.project_role == REQUIRED_DELIVERY_ROLE,
        )
        .execution_options(populate_existing=True)
    ).all()
    return {r[0] for r in rows}


def lock_for_account_change(db: Session, user_id) -> list:
    """Discover broadly (unlocked, provisional) -> lock levels 1-5 for the candidates then the User
    rows -> revalidate the membership set; if a concurrent assignment added a project, ROLL BACK and
    retry from discovery (never taking a Project lock after User locks). Bounded by RETRY_LIMIT."""
    for _attempt in range(RETRY_LIMIT):
        candidates = _discover_site_engineer_projects(db, user_id)
        if _after_discovery_hook is not None:
            _after_discovery_hook()
        lock_project_scope(db, candidates, user_ids=[user_id])
        if _discover_site_engineer_projects(db, user_id) <= candidates:
            return sorted(candidates)
        db.rollback()
    raise HTTPException(
        status_code=503,
        detail="The account change could not be applied because project teams kept changing; please retry",
        headers={"Retry-After": "1"},
    )


def finalize_account_change(
    db: Session, project_ids, reason: str, actor: User, request: Request | None
) -> list:
    return invalidate_if_no_eligible_engineer(db, project_ids, reason, actor, request)


# --------------------------------------------------------------------------- access helpers


def is_active_team_member(db: Session, project_id, user_id) -> ProjectTeamMember | None:
    return db.execute(
        select(ProjectTeamMember).where(
            ProjectTeamMember.project_id == project_id,
            ProjectTeamMember.user_id == user_id,
            ProjectTeamMember.removed_at.is_(None),
        )
    ).scalars().first()
