import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_log import AuditLogEntryOut
from app.core import follow_up_entities, ownership, project_status
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLogEntry
from app.models.client import Client
from app.models.document import Estimate, EstimateStatus, Quotation, QuotationStatus
from app.models.follow_up import TERMINAL_FOLLOW_UP_STATUSES
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.project import Project
from app.models.user import User, UserRole
from app.services import payments as payments_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Amendment 50: the roles that may open the Payments header (see payments.py).
PAYMENTS_ROLES = ("pm", "director", "ca_tax")

# Amendment 4 (Annexure 2): "business-summary dashboard ... the app itself
# is the training." Recent activity reuses the audit log's own existing
# role gate (Director-only, per audit_log.py's own documented reasoning)
# rather than exposing that feed to every role just because it's now
# embedded in a page everyone sees.
RECENT_PROJECTS_LIMIT = 8
RECENT_ACTIVITY_LIMIT = 10


class DashboardSummary(BaseModel):
    open_projects_count: int
    pending_estimates_count: int
    pending_quotations_count: int
    overdue_clients_count: int
    followups_due_count: int
    # Amendment 44 Phase D: real counts behind the "Open opportunities" tile
    # and the "Sales pipeline" panel. Counts only -- an Opportunity has no
    # estimate/quotation value yet, and showing one would be fabricated.
    open_opportunities_count: int
    opportunities_new_count: int
    opportunities_contacted_count: int
    opportunities_qualified_count: int
    won_this_month_total: float


class RecentProjectOut(BaseModel):
    id: uuid.UUID
    project_no: str
    client_name: str
    city: str
    created_at: datetime


class PaymentsMonthOut(BaseModel):
    month: str  # "YYYY-MM"
    awarded_value: float
    cash_received: float


class PaymentsOverview(BaseModel):
    """Amendment 50 (Section 54): behind the Overview's "Payments overdue"
    tile and "Orders & collections" panel. Every figure is derived by
    app.services.payments from entered milestones and receipts -- nothing is
    estimated. overdue_count is the number of Work Orders with an overdue
    milestone (the same number the Payments screen's Overdue tab lists);
    tracked_milestones_count is 0 until someone enters a due date, and the
    screen then shows "--", never a fabricated zero."""

    tracked_milestones_count: int
    overdue_count: int
    overdue_milestones_count: int
    overdue_amount: float
    work_orders_count: int
    awarded_value_total: float
    cash_received_total: float
    tds_total: float
    outstanding_total: float
    months: list[PaymentsMonthOut]


class SalespersonRowOut(BaseModel):
    """One salesperson's own numbers -- the same figures their own Overview shows (Amendment 60)."""

    user_id: uuid.UUID
    name: str
    open_projects_count: int
    pending_quotations_count: int
    open_opportunities_count: int
    followups_due_count: int
    won_this_month_total: float


class DashboardOut(BaseModel):
    summary: DashboardSummary
    recent_projects: list[RecentProjectOut]
    # None for roles that cannot open the Payments header (everyone but
    # pm / director / ca_tax) -- same "return only what the role may see"
    # rule as recent_activity below.
    payments: PaymentsOverview | None = None
    # Amendment 60: "own" when the numbers above are this person's own records, "company" when they are the company's.
    scope: str = "company"
    # Amendment 60: a row per active salesperson, for the PM and Director only (None for every other role).
    sales_performance: list[SalespersonRowOut] | None = None
    # None for every role but Director -- matches audit_log.py's own
    # Director-only gate rather than inventing a broader one here.
    recent_activity: list[AuditLogEntryOut] | None


def _summary(db: Session, owner: uuid.UUID | None, followups_viewer: User) -> DashboardSummary:
    """The Overview's numbers -- for the whole company (owner None), or for one person's own records (Amendment 60,
    Section 63: a salesperson's dashboard is their own performance, never the company's, and the same function fills
    the Director's per-salesperson table).

    followups_due_count is derived from app.core.follow_up_entities.visible_follow_ups(db, followups_viewer) --
    the exact same shared visibility rule GET /follow-ups' own no-filter listing uses (correction plan,
    2026-09-29) -- rather than the legacy Client/Opportunity.next_follow_up_date columns filtered by `owner`.
    Two earlier, independent bugs both traced back to that legacy computation not actually matching the
    destination screen's own rules: (1) it ignored the Amendment 60 switch's effect on the destination's
    unconditional Sales narrowing, and (2) even once scoped correctly by owner_id, it never re-checked whether
    the viewer could still actually open the record (an explicitly assigned specialist, or a follow-up whose
    owner_id has drifted from its parent's current owner after a reassignment) -- the same access check the
    destination list has always applied per row. Passing the real viewer through directly, rather than a bare
    owner id, means the two can no longer independently drift: get_dashboard() passes current_user (whatever
    that role is); _sales_performance() passes each salesperson being summarised, not the Director browsing
    their table, so each row still reflects what that salesperson would see, not what the Director would."""
    # Amendment 28 Part A: "closed" means *every* Quotation on the project
    # has reached Won/Lost, not just any -- a project with a newer,
    # currently-active Quotation is Open regardless of an older Lost one
    # (e.g. a re-bid, which Amendment 26 made possible). A project with no
    # Quotations at all is never closed, unaffected by this fix.
    # The rule itself now lives in app/core/project_status.py, shared with GET /projects so the tile and the list
    # it opens cannot disagree.
    closed_project_ids = project_status.closed_project_ids(db)
    open_projects = db.query(Project).filter(~Project.id.in_(closed_project_ids), Project.is_calibration.is_(False))
    if owner is not None:
        open_projects = open_projects.filter(Project.owner_id == owner)
    open_projects_count = open_projects.count()

    # "Pending" an estimate = sent to the client, awaiting a response --
    # Draft hasn't gone out yet, Superseded/Expired are no longer live.
    # Amendment 28 Part B: calibration/test projects never contribute to
    # any of the three summary tiles.
    pending_estimates = (
        db.query(Estimate)
        .join(Project, Project.id == Estimate.project_id)
        .filter(Estimate.status == EstimateStatus.SENT, Project.is_calibration.is_(False))
    )
    if owner is not None:
        pending_estimates = pending_estimates.filter(Project.owner_id == owner)
    pending_estimates_count = pending_estimates.count()

    pending_quotations = (
        db.query(Quotation)
        .join(Project, Project.id == Quotation.project_id)
        .filter(
            Quotation.status.in_(
                [QuotationStatus.DRAFT, QuotationStatus.RELEASED, QuotationStatus.SENT]
            ),
            Project.is_calibration.is_(False),
        )
    )
    if owner is not None:
        pending_quotations = pending_quotations.filter(Project.owner_id == owner)
    pending_quotations_count = pending_quotations.count()

    overdue_clients = db.query(Client).filter(Client.overdue_flag.is_(True))
    if owner is not None:
        overdue_clients = overdue_clients.filter(Client.owner_id == owner)
    overdue_clients_count = overdue_clients.count()

    # Amendment 43 (Section E step 4): "due" includes due-today, not just
    # strictly overdue -- matches the overdue-red convention Amendment 42's
    # Client Admin follow-up row already uses (< today, not <= today, shown
    # red; today itself is "due" rather than "overdue"). Terminal-status rows
    # (completed/cancelled) are excluded the same way TERMINAL_FOLLOW_UP_STATUSES
    # excludes them everywhere else this model is queried.
    today = date.today()
    stage_query = db.query(Opportunity.stage, func.count(Opportunity.id))
    if owner is not None:
        stage_query = stage_query.filter(Opportunity.owner_id == owner)
    followups_due_count = sum(
        1
        for f in follow_up_entities.visible_follow_ups(db, followups_viewer)
        if f.status not in TERMINAL_FOLLOW_UP_STATUSES and f.due_date <= today
    )

    stage_counts = dict(stage_query.group_by(Opportunity.stage).all())
    opportunities_new_count = stage_counts.get(OpportunityStage.NEW, 0)
    opportunities_contacted_count = stage_counts.get(OpportunityStage.CONTACTED, 0)
    opportunities_qualified_count = stage_counts.get(OpportunityStage.QUALIFIED, 0)
    open_opportunities_count = (
        opportunities_new_count + opportunities_contacted_count + opportunities_qualified_count
    )

    # Quotation has no dedicated "won_at" timestamp (same gap reports.py's
    # own Pipeline report documents) -- released_at is the same proxy
    # period-anchor reports.py already uses for this schema, kept
    # consistent here rather than inventing a second convention.
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    won = (
        db.query(func.coalesce(func.sum(Quotation.quotation_total), 0))
        .filter(Quotation.status == QuotationStatus.WON)
        .filter(Quotation.released_at.isnot(None))
        .filter(Quotation.released_at >= month_start)
    )
    if owner is not None:
        won = won.join(Project, Project.id == Quotation.project_id).filter(Project.owner_id == owner)
    won_this_month_total = won.scalar()

    return DashboardSummary(
        open_projects_count=open_projects_count,
        pending_estimates_count=pending_estimates_count,
        pending_quotations_count=pending_quotations_count,
        overdue_clients_count=overdue_clients_count,
        followups_due_count=followups_due_count,
        open_opportunities_count=open_opportunities_count,
        opportunities_new_count=opportunities_new_count,
        opportunities_contacted_count=opportunities_contacted_count,
        opportunities_qualified_count=opportunities_qualified_count,
        won_this_month_total=float(won_this_month_total),
    )


def _sales_performance(db: Session) -> list["SalespersonRowOut"]:
    """Amendment 60 item 6: one row per active salesperson, from the very same numbers their own dashboard shows."""
    rows = []
    for person in db.query(User).filter(User.role == UserRole.SALES, User.is_active.is_(True)).order_by(User.name).all():
        s = _summary(db, person.id, followups_viewer=person)
        rows.append(
            SalespersonRowOut(
                user_id=person.id,
                name=person.name,
                open_projects_count=s.open_projects_count,
                pending_quotations_count=s.pending_quotations_count,
                open_opportunities_count=s.open_opportunities_count,
                followups_due_count=s.followups_due_count,
                won_this_month_total=s.won_this_month_total,
            )
        )
    return rows


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("sales", "pm", "director", "procurement", "site_engineer", "ca_tax")
    ),
):
    # Amendment 60: a salesperson's dashboard (once the Director has switched own-records on) is their own numbers.
    owner = current_user.id if ownership.scoping_applies(db, current_user) else None
    # followups_due_count always reflects current_user's own visible_follow_ups() result (see _summary()'s own
    # docstring) -- a Sales user is narrowed to their own rows by that shared rule regardless of `owner` above.
    summary = _summary(db, owner, followups_viewer=current_user)

    recent_query = db.query(Project, Client.name).join(Client, Client.id == Project.client_id)
    if owner is not None:
        recent_query = recent_query.filter(Project.owner_id == owner)
    recent_rows = recent_query.order_by(Project.created_at.desc()).limit(RECENT_PROJECTS_LIMIT).all()
    recent_projects = [
        RecentProjectOut(
            id=project.id,
            project_no=project.project_no,
            client_name=client_name,
            city=project.city,
            created_at=project.created_at,
        )
        for project, client_name in recent_rows
    ]

    recent_activity = None
    if current_user.role == UserRole.DIRECTOR:
        entries = (
            db.query(AuditLogEntry)
            .order_by(AuditLogEntry.timestamp.desc())
            .limit(RECENT_ACTIVITY_LIMIT)
            .all()
        )
        recent_activity = [AuditLogEntryOut.model_validate(e) for e in entries]

    return DashboardOut(
        summary=summary,
        scope="own" if owner is not None else "company",
        recent_projects=recent_projects,
        recent_activity=recent_activity,
        sales_performance=_sales_performance(db) if current_user.role.value in ("pm", "director") else None,
        payments=(
            PaymentsOverview(**payments_service.build_overview(db, date.today()))
            if current_user.role.value in PAYMENTS_ROLES
            else None
        ),
    )
