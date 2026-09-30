"""Amendment 60 (Section 63): who owns which client, project and enquiry -- the review, the reassigning, the switch.

PM and Director see who owns what, see the records that have no owner yet (with a suggestion where the data points to
one), and assign them -- one at a time, all of one person's at once, or by accepting the suggestions. Only the
Director turns own-records on. Every change is written to the audit log. Nothing here is visible to any other role."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.settings import get_current_setting_value
from app.core import follow_up_entities
from app.core import follow_up_sync
from app.core import ownership
from app.core.auth import require_roles
from app.core.reminders import _get_or_create_notification, resolve_entity_label
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Quotation
from app.models.follow_up import TERMINAL_FOLLOW_UP_STATUSES, FollowUp, FollowUpEntityType
from app.models.notification import NotificationKind
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.setting import Setting, SettingScope
from app.models.user import User, UserRole

# Dashboard-fix follow-up (correction plan, 2026-09-29): a Client, Opportunity or Project
# reassignment carries its record's own open, inherited FollowUp rows along with it. "Inherited"
# is the FollowUp model's own distinction (see FollowUp.owner_explicitly_assigned's docstring): a
# row nobody deliberately pointed elsewhere just reflects whoever currently owns the parent. An
# explicitly assigned specialist's row is never touched here -- same rule the model's own
# docstring already stated before this cascade existed to enforce it. Completed/cancelled rows
# are historical record and are not touched either way. Project IS covered: FollowUpEntityType.PROJECT
# is a real, used entity type (project_overview.py, follow_up_entities.py's own resolve_entity,
# reminders.py); create_follow_up (app/api/follow_ups.py) defaults a manually created Project
# follow-up's owner_id from the Project's own current owner_id the same uniform way it does for
# Client/Opportunity, so the inherited-vs-explicit rule already governs Project follow-ups today
# and reassignment must honour it the same way. follow_up_sync.py's mirror_legacy_columns being
# CLIENT/OPPORTUNITY-only is unrelated -- that mirrors the FollowUp table back onto the two legacy
# next_follow_up_date columns Project never had, not whether Project follow-ups exist or cascade.
_FOLLOW_UP_ENTITY_TYPE = {
    "client": FollowUpEntityType.CLIENT,
    "opportunity": FollowUpEntityType.OPPORTUNITY,
    "project": FollowUpEntityType.PROJECT,
}


def _flag_specialist_access_mismatches(db: Session, entity_type: FollowUpEntityType, entity_id: uuid.UUID) -> None:
    """The explicit assignments _cascade_inherited_follow_ups deliberately left alone can still be
    broken by the same reassignment: an explicitly assigned specialist's own read access to the
    parent (check_follow_up_access) is resolved fresh each time, from the parent's CURRENT owner
    and the Amendment 60 switch -- so a parent reassignment can silently strand a specialist who
    could open their follow-up a moment ago and can't now. Flags it immediately, the same way (and
    to the same Directors, via the same idempotent, deduplicated notification) reminders.py's own
    daily run already flags any due-or-overdue access mismatch -- reused here, not reimplemented,
    so a still-future-dated one doesn't have to wait for its due date before anyone finds out."""
    active_directors = db.query(User).filter(User.role == UserRole.DIRECTOR, User.is_active.is_(True)).all()
    if not active_directors:
        return
    explicit_open = (
        db.query(FollowUp)
        .filter(
            FollowUp.entity_type == entity_type,
            FollowUp.entity_id == entity_id,
            FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
            FollowUp.owner_explicitly_assigned.is_(True),
            FollowUp.owner_id.isnot(None),
        )
        .all()
    )
    today = date.today()
    for fu in explicit_open:
        owner = db.query(User).filter(User.id == fu.owner_id).first()
        if owner is None or not owner.is_active:
            continue
        try:
            follow_up_entities.check_follow_up_access(db, owner, fu.entity_type, fu.entity_id, need="read")
            continue  # still fine -- nothing to flag
        except HTTPException as exc:
            reason = (
                "Amendment 60's own-records setting restricting it to the record's owner"
                if exc.status_code == 404
                else f"{owner.role.value}'s role has no read access to this kind of record at all"
            )
        label = resolve_entity_label(db, fu.entity_type, fu.entity_id)
        contact = owner.email or owner.mobile or "no contact on file"
        for director in active_directors:
            _get_or_create_notification(
                db, user_id=director.id, follow_up_id=fu.id, kind=NotificationKind.ACCESS_MISMATCH_ESCALATION,
                notification_date=today,
                title=f"Access mismatch: {owner.name} cannot open their own follow-up",
                body=(
                    f"{owner.name} ({contact}) is assigned \"{fu.next_action}\" on {label}, due "
                    f"{fu.due_date.isoformat()}, but does not currently have access to open it "
                    f"(likely {reason} -- this record was just reassigned). Not emailed to them -- "
                    f"review the assignment or ownership directly."
                ),
                entity_type=fu.entity_type, entity_id=fu.entity_id,
            )


def _cascade_inherited_follow_ups(db: Session, kind: str, entity_id: uuid.UUID, new_owner: uuid.UUID | None) -> None:
    entity_type = _FOLLOW_UP_ENTITY_TYPE.get(kind)
    if entity_type is None or follow_up_sync.follow_up_writes_locked(db):
        return
    open_inherited = db.query(FollowUp).filter(
        FollowUp.entity_type == entity_type,
        FollowUp.entity_id == entity_id,
        FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES),
        FollowUp.owner_explicitly_assigned.is_(False),
    )
    for follow_up in open_inherited.all():
        follow_up.owner_id = new_owner
    _flag_specialist_access_mismatches(db, entity_type, entity_id)


ownership_router = APIRouter(prefix="/ownership", tags=["ownership"])

REVIEW_ROLES = ("pm", "director")
KINDS = {"client": Client, "project": Project, "opportunity": Opportunity}
UNASSIGNED_LIMIT = 500


def _model(kind: str):
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail="Unknown kind of record")
    return KINDS[kind]


def _name(db: Session, user_id: uuid.UUID | None, cache: dict) -> str | None:
    if user_id is None:
        return None
    if user_id not in cache:
        user = db.get(User, user_id)
        cache[user_id] = user.name if user else "Unknown"
    return cache[user_id]


class OwnerOption(BaseModel):
    user_id: uuid.UUID
    name: str
    role: str


class KindTotals(BaseModel):
    total: int
    unassigned: int


class OwnerRow(BaseModel):
    user_id: uuid.UUID
    name: str
    role: str
    is_active: bool
    clients: int
    projects: int
    opportunities: int


class OwnershipOverviewOut(BaseModel):
    switch_on: bool
    totals: dict[str, KindTotals]
    by_owner: list[OwnerRow]
    owners: list[OwnerOption]  # who a record may be assigned to


@ownership_router.get("/overview", response_model=OwnershipOverviewOut)
def get_overview(db: Session = Depends(get_db), current_user=Depends(require_roles(*REVIEW_ROLES))):
    totals = {}
    counts: dict[str, dict[uuid.UUID, int]] = {}
    for kind, model in KINDS.items():
        total = db.query(func.count(model.id)).scalar()
        unassigned = db.query(func.count(model.id)).filter(model.owner_id.is_(None)).scalar()
        totals[kind] = KindTotals(total=total, unassigned=unassigned)
        counts[kind] = dict(
            db.query(model.owner_id, func.count(model.id)).filter(model.owner_id.isnot(None)).group_by(model.owner_id).all()
        )
    owner_ids = {uid for per_kind in counts.values() for uid in per_kind}
    rows = []
    for user in db.query(User).filter(User.id.in_(owner_ids)).order_by(User.name).all() if owner_ids else []:
        rows.append(
            OwnerRow(
                user_id=user.id, name=user.name, role=user.role.value, is_active=user.is_active,
                clients=counts["client"].get(user.id, 0),
                projects=counts["project"].get(user.id, 0),
                opportunities=counts["opportunity"].get(user.id, 0),
            )
        )
    eligible = (
        db.query(User)
        .filter(User.is_active.is_(True), User.role.in_(ownership.OWNER_ROLES))
        .order_by(User.name)
        .all()
    )
    return OwnershipOverviewOut(
        switch_on=ownership.switch_is_on(db),
        totals=totals,
        by_owner=rows,
        owners=[OwnerOption(user_id=u.id, name=u.name, role=u.role.value) for u in eligible],
    )


class UnassignedRow(BaseModel):
    id: uuid.UUID
    label: str
    detail: str | None
    created_at: date | None
    suggested_owner_id: uuid.UUID | None = None
    suggested_owner_name: str | None = None
    evidence: str | None = None


def _suggest_for_project(db: Session, project: Project) -> tuple[uuid.UUID | None, str | None]:
    """A weaker signal than an enquiry link: a salesperson created a quotation on it. Suggested, never applied alone."""
    quotation = (
        db.query(Quotation)
        .join(User, User.id == Quotation.created_by_id)
        .filter(Quotation.project_id == project.id, User.role == UserRole.SALES, User.is_active.is_(True))
        .order_by(Quotation.created_at.asc())
        .first()
    )
    if quotation is None:
        return None, None
    return quotation.created_by_id, "a salesperson created a quotation on it"


def _suggest_for_client(db: Session, client: Client) -> tuple[uuid.UUID | None, str | None]:
    owners = {
        o for (o,) in db.query(Project.owner_id).filter(Project.client_id == client.id, Project.owner_id.isnot(None)).all()
    }
    if len(owners) == 1:
        return next(iter(owners)), "all its owned projects belong to this person"
    return None, None


def _unassigned_rows(db: Session, kind: str) -> list[UnassignedRow]:
    model = _model(kind)
    records = db.query(model).filter(model.owner_id.is_(None)).order_by(model.created_at.desc()).limit(UNASSIGNED_LIMIT).all()
    names: dict = {}
    rows = []
    for record in records:
        suggested, evidence = (None, None)
        if kind == "project":
            client = db.get(Client, record.client_id)
            label, detail = record.project_no, " · ".join(x for x in (client.name if client else None, record.city) if x)
            suggested, evidence = _suggest_for_project(db, record)
        elif kind == "client":
            label, detail = record.name, " · ".join(x for x in (record.city, record.phone) if x)
            suggested, evidence = _suggest_for_client(db, record)
        else:
            label, detail = record.lead_name, record.lead_phone
        rows.append(
            UnassignedRow(
                id=record.id, label=label, detail=detail or None,
                created_at=record.created_at.date() if record.created_at else None,
                suggested_owner_id=suggested, suggested_owner_name=_name(db, suggested, names), evidence=evidence,
            )
        )
    return rows


@ownership_router.get("/unassigned", response_model=list[UnassignedRow])
def list_unassigned(kind: str, db: Session = Depends(get_db), current_user=Depends(require_roles(*REVIEW_ROLES))):
    return _unassigned_rows(db, kind)


class ReassignRequest(BaseModel):
    owner_id: uuid.UUID | None = None  # None = make it unassigned
    cascade: bool = True  # a client's own projects and enquiries follow it


def _set_owner(db, request, current_user, kind, record, new_owner, reason=None) -> None:
    old = record.owner_id
    if old == new_owner:
        return
    record.owner_id = new_owner
    names: dict = {}
    write_audit_log_entry(
        db, current_user, kind, record.id, "owner",
        old_value=_name(db, old, names) or "(unassigned)", new_value=_name(db, new_owner, names) or "(unassigned)",
        reason=reason, request=request,
    )
    _cascade_inherited_follow_ups(db, kind, record.id, new_owner)


@ownership_router.patch("/{kind}/{record_id}", response_model=KindTotals)
def reassign_record(
    kind: str,
    record_id: uuid.UUID,
    payload: ReassignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REVIEW_ROLES)),
):
    model = _model(kind)
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    if payload.owner_id is not None:
        ownership.require_valid_owner(db, payload.owner_id)
    old = record.owner_id
    _set_owner(db, request, current_user, kind, record, payload.owner_id)
    if kind == "client" and payload.cascade:
        # what belonged to the old owner (or to nobody) under this client moves with it
        for child_kind, child_model in (("project", Project), ("opportunity", Opportunity)):
            query = db.query(child_model).filter(child_model.client_id == record.id)
            for child in query.all():
                if child.owner_id == old or child.owner_id is None:
                    _set_owner(db, request, current_user, child_kind, child, payload.owner_id, "moved with its client")
    db.commit()
    total = db.query(func.count(model.id)).scalar()
    return KindTotals(total=total, unassigned=db.query(func.count(model.id)).filter(model.owner_id.is_(None)).scalar())


class ReassignAllRequest(BaseModel):
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID


class ReassignAllOut(BaseModel):
    clients: int
    projects: int
    opportunities: int


@ownership_router.post("/reassign-all", response_model=ReassignAllOut)
def reassign_all(
    payload: ReassignAllRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REVIEW_ROLES)),
):
    """Everything one person owns goes to another -- what to do when someone leaves or changes role."""
    if payload.from_user_id == payload.to_user_id:
        raise HTTPException(status_code=422, detail="Choose two different people")
    ownership.require_valid_owner(db, payload.to_user_id)
    moved = {}
    for kind, model in KINDS.items():
        rows = db.query(model).filter(model.owner_id == payload.from_user_id).all()
        for row in rows:
            _set_owner(db, request, current_user, kind, row, payload.to_user_id, "all of one person's records moved")
        moved[kind] = len(rows)
    db.commit()
    return ReassignAllOut(clients=moved["client"], projects=moved["project"], opportunities=moved["opportunity"])


class AcceptSuggestionsRequest(BaseModel):
    kind: str


@ownership_router.post("/accept-suggestions", response_model=KindTotals)
def accept_suggestions(
    payload: AcceptSuggestionsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*REVIEW_ROLES)),
):
    model = _model(payload.kind)
    for row in _unassigned_rows(db, payload.kind):
        if row.suggested_owner_id is not None:
            record = db.get(model, row.id)
            _set_owner(db, request, current_user, payload.kind, record, row.suggested_owner_id, f"accepted suggestion: {row.evidence}")
    db.commit()
    total = db.query(func.count(model.id)).scalar()
    return KindTotals(total=total, unassigned=db.query(func.count(model.id)).filter(model.owner_id.is_(None)).scalar())


class SwitchRequest(BaseModel):
    on: bool


class SwitchOut(BaseModel):
    switch_on: bool


@ownership_router.put("/switch", response_model=SwitchOut)
def set_switch(
    payload: SwitchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("director")),
):
    """The Director's decision, and only theirs: from now on a Sales user sees only what they own (or not). It is a
    Master Setting version like any other, so it is in the settings history and the audit log."""
    old = get_current_setting_value(db, ownership.SWITCH_KEY)
    value = "on" if payload.on else "off"
    setting = Setting(
        key=ownership.SWITCH_KEY, scope=SettingScope.GLOBAL, scope_value=None, value=value, unit=None,
        effective_from=date.today(), changed_by_id=current_user.id,
        reason="Own-records visibility for Sales switched " + value,
    )
    db.add(setting)
    db.flush()
    write_audit_log_entry(
        db, current_user, "setting", setting.id, ownership.SWITCH_KEY,
        old_value=old or "off", new_value=value, reason=setting.reason, request=request,
    )
    db.commit()
    return SwitchOut(switch_on=payload.on)
