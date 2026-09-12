import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.audit_log import AuditLogEntryOut
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLogEntry
from app.models.client import Client
from app.models.document import Estimate, EstimateStatus, Quotation, QuotationStatus
from app.models.project import Project
from app.models.user import User, UserRole

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

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
    won_this_month_total: float


class RecentProjectOut(BaseModel):
    id: uuid.UUID
    project_no: str
    client_name: str
    city: str
    created_at: datetime


class DashboardOut(BaseModel):
    summary: DashboardSummary
    recent_projects: list[RecentProjectOut]
    # None for every role but Director -- matches audit_log.py's own
    # Director-only gate rather than inventing a broader one here.
    recent_activity: list[AuditLogEntryOut] | None


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("sales", "pm", "director", "procurement", "site_engineer", "ca_tax")
    ),
):
    # "Open" = no Quotation on the project has reached a closed status yet
    # (Won/Lost) -- the same WON/LOST vocabulary reports.py's Pipeline
    # report already uses for this schema.
    closed_project_ids = (
        db.query(Quotation.project_id)
        .filter(Quotation.status.in_([QuotationStatus.WON, QuotationStatus.LOST]))
        .distinct()
    )
    open_projects_count = (
        db.query(Project).filter(~Project.id.in_(closed_project_ids)).count()
    )

    # "Pending" an estimate = sent to the client, awaiting a response --
    # Draft hasn't gone out yet, Superseded/Expired are no longer live.
    pending_estimates_count = (
        db.query(Estimate).filter(Estimate.status == EstimateStatus.SENT).count()
    )

    pending_quotations_count = (
        db.query(Quotation)
        .filter(
            Quotation.status.in_(
                [QuotationStatus.DRAFT, QuotationStatus.RELEASED, QuotationStatus.SENT]
            )
        )
        .count()
    )

    overdue_clients_count = db.query(Client).filter(Client.overdue_flag.is_(True)).count()

    # Quotation has no dedicated "won_at" timestamp (same gap reports.py's
    # own Pipeline report documents) -- released_at is the same proxy
    # period-anchor reports.py already uses for this schema, kept
    # consistent here rather than inventing a second convention.
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    won_this_month_total = (
        db.query(func.coalesce(func.sum(Quotation.quotation_total), 0))
        .filter(Quotation.status == QuotationStatus.WON)
        .filter(Quotation.released_at.isnot(None))
        .filter(Quotation.released_at >= month_start)
        .scalar()
    )

    recent_rows = (
        db.query(Project, Client.name)
        .join(Client, Client.id == Project.client_id)
        .order_by(Project.created_at.desc())
        .limit(RECENT_PROJECTS_LIMIT)
        .all()
    )
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
        summary=DashboardSummary(
            open_projects_count=open_projects_count,
            pending_estimates_count=pending_estimates_count,
            pending_quotations_count=pending_quotations_count,
            overdue_clients_count=overdue_clients_count,
            won_this_month_total=float(won_this_month_total),
        ),
        recent_projects=recent_projects,
        recent_activity=recent_activity,
    )
