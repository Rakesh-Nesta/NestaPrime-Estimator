import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.api.clients import READ_ROLES as CLIENT_READ_ROLES
from app.api.documents import _effective_quotation_status
from app.api.opportunities import READ_ROLES as OPPORTUNITY_READ_ROLES
from app.api.projects import LIST_ROLES as PROJECT_LIST_ROLES
from app.api.quotations_admin import LIST_ROLES as QUOTATION_LIST_ROLES
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Quotation
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.project import Project
from app.models.user import UserRole

router = APIRouter(prefix="/search", tags=["search"])

# Amendment 53 (Section 57): global quick search -- one box that finds a client,
# a lead, a project or a quotation. It must never show a role more than the role
# could already open, so each kind of result is gated by the very constants the
# corresponding list endpoint enforces (tests/test_search.py checks they still
# match the live route gates), and no result carries a cost, margin, price or any
# amount (K.3): a result identifies a record, it does not describe it.
ALL_ROLES = tuple(role.value for role in UserRole)
MIN_QUERY_LENGTH = 2
GROUP_LIMIT = 6
MIN_PHONE_DIGITS = 3

# Whole query looks like a phone number (digits and the usual separators).
_PHONE_LIKE = re.compile(r"[\d\s+().-]+")


class SearchItemOut(BaseModel):
    kind: str
    id: uuid.UUID
    primary: str
    secondary: str | None
    client_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None


class SearchGroupOut(BaseModel):
    kind: str
    label: str
    total: int
    items: list[SearchItemOut]


class SearchOut(BaseModel):
    query: str
    limit: int
    groups: list[SearchGroupOut]


def _like_pattern(text: str) -> str:
    """`%` and `_` typed by the user are matched literally, never as wildcards."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _prefix_pattern(text: str) -> str:
    return _like_pattern(text)[1:]  # same escaping, anchored at the start


def _phone_digits(query: str) -> str | None:
    """Digits of a phone-like query, or None. Only a query made entirely of digits
    and phone punctuation, with at least MIN_PHONE_DIGITS digits, is matched
    against phone numbers by digits ("98765 43210" finds "+91-98765-43210");
    "Project 2026" is not treated as a phone number."""
    if not _PHONE_LIKE.fullmatch(query):
        return None
    digits = re.sub(r"\D", "", query)
    return digits if len(digits) >= MIN_PHONE_DIGITS else None


def _any(conditions):
    return or_(*conditions)


def _digits_of(column):
    return func.regexp_replace(column, "[^0-9]", "", "g")


def _rank(primary_column, query: str):
    """Exact matches first, then prefix matches, then the rest."""
    lowered = func.lower(primary_column)
    return case(
        (lowered == query.lower(), 0),
        (lowered.like(_prefix_pattern(query.lower()), escape="\\"), 1),
        else_=2,
    )


def _title(value) -> str:
    text = value.value if hasattr(value, "value") else str(value)
    return text.replace("_", " ").capitalize()


def _joined(parts) -> str | None:
    text = " · ".join(part for part in parts if part)
    return text or None


def _clients(db: Session, query: str, phone_digits: str | None) -> SearchGroupOut:
    pattern = _like_pattern(query)
    conditions = [
        column.ilike(pattern, escape="\\")
        for column in (Client.name, Client.contact_name, Client.phone, Client.email, Client.city)
    ]
    if phone_digits:
        conditions.append(_digits_of(Client.phone).like(f"%{phone_digits}%"))
    q = db.query(Client).filter(_any(conditions))
    total = q.count()
    rows = q.order_by(_rank(Client.name, query), Client.created_at.desc(), Client.id).limit(GROUP_LIMIT).all()
    items = [
        SearchItemOut(
            kind="client", id=c.id, primary=c.name,
            secondary=_joined([c.phone, c.city, _title(c.type)]), client_id=c.id,
        )
        for c in rows
    ]
    return SearchGroupOut(kind="client", label="Clients", total=total, items=items)


def _leads(db: Session, query: str, phone_digits: str | None) -> SearchGroupOut:
    # The same set Leads & Clients lists as leads (not linked to a client, not lost),
    # so a result always lands where the record is shown.
    pattern = _like_pattern(query)
    conditions = [
        column.ilike(pattern, escape="\\")
        for column in (Opportunity.lead_name, Opportunity.lead_phone, Opportunity.lead_email)
    ]
    if phone_digits:
        conditions.append(_digits_of(Opportunity.lead_phone).like(f"%{phone_digits}%"))
    q = db.query(Opportunity).filter(
        Opportunity.client_id.is_(None), Opportunity.stage != OpportunityStage.LOST, _any(conditions)
    )
    total = q.count()
    rows = (
        q.order_by(_rank(Opportunity.lead_name, query), Opportunity.created_at.desc(), Opportunity.id)
        .limit(GROUP_LIMIT)
        .all()
    )
    items = [
        SearchItemOut(
            kind="lead", id=o.id, primary=o.lead_name,
            secondary=_joined([o.lead_phone, _title(o.stage)]), opportunity_id=o.id,
        )
        for o in rows
    ]
    return SearchGroupOut(kind="lead", label="Leads", total=total, items=items)


def _projects(db: Session, query: str) -> SearchGroupOut:
    pattern = _like_pattern(query)
    q = (
        db.query(Project, Client.name)
        .join(Client, Client.id == Project.client_id)
        .filter(
            _any(
                [
                    Project.project_no.ilike(pattern, escape="\\"),
                    Client.name.ilike(pattern, escape="\\"),
                    Project.city.ilike(pattern, escape="\\"),
                ]
            )
        )
    )
    total = q.count()
    rows = q.order_by(_rank(Project.project_no, query), Project.created_at.desc(), Project.id).limit(GROUP_LIMIT).all()
    items = [
        SearchItemOut(
            kind="project", id=p.id, primary=p.project_no,
            secondary=_joined([client_name, p.city]), client_id=p.client_id, project_id=p.id,
        )
        for p, client_name in rows
    ]
    return SearchGroupOut(kind="project", label="Projects", total=total, items=items)


def _quotations(db: Session, query: str) -> SearchGroupOut:
    pattern = _like_pattern(query)
    q = (
        db.query(Quotation, Project, Client.name)
        .join(Project, Project.id == Quotation.project_id)
        .join(Client, Client.id == Project.client_id)
        .filter(
            _any(
                [
                    Quotation.document_no.ilike(pattern, escape="\\"),
                    Project.project_no.ilike(pattern, escape="\\"),
                    Client.name.ilike(pattern, escape="\\"),
                ]
            )
        )
    )
    total = q.count()
    rows = (
        q.order_by(_rank(Quotation.document_no, query), Quotation.created_at.desc(), Quotation.id)
        .limit(GROUP_LIMIT)
        .all()
    )
    # document number, client, project number and status -- never an amount.
    items = [
        SearchItemOut(
            kind="quotation", id=quotation.id, primary=quotation.document_no,
            secondary=_joined([client_name, project.project_no, _title(_effective_quotation_status(quotation))]),
            client_id=project.client_id, project_id=project.id,
        )
        for quotation, project, client_name in rows
    ]
    return SearchGroupOut(kind="quotation", label="Quotations", total=total, items=items)


@router.get("", response_model=SearchOut)
def global_search(
    q: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ALL_ROLES)),
):
    """One box for the header: clients, leads, projects and quotations, each group
    capped at GROUP_LIMIT with its true total. A role receives only the kinds it
    can already read."""
    query = q.strip()
    if len(query) < MIN_QUERY_LENGTH:
        raise HTTPException(
            status_code=422, detail=f"Type at least {MIN_QUERY_LENGTH} characters to search"
        )
    role = current_user.role.value
    phone_digits = _phone_digits(query)

    groups: list[SearchGroupOut] = []
    if role in CLIENT_READ_ROLES:
        groups.append(_clients(db, query, phone_digits))
    if role in OPPORTUNITY_READ_ROLES:
        groups.append(_leads(db, query, phone_digits))
    if role in PROJECT_LIST_ROLES:
        groups.append(_projects(db, query))
    if role in QUOTATION_LIST_ROLES:
        groups.append(_quotations(db, query))
    return SearchOut(query=query, limit=GROUP_LIMIT, groups=groups)
