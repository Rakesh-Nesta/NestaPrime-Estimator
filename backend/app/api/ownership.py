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
from app.core import ownership
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Quotation
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.setting import Setting, SettingScope
from app.models.user import User, UserRole

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
