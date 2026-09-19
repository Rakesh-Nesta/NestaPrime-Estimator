import csv
import io
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.documents import _effective_quotation_status
from app.api.reports import _sports_for_quotation
from app.core.auth import require_roles
from app.core.export_safety import sanitize_row
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Quotation, QuotationStatus
from app.models.project import Project

quotations_admin_router = APIRouter(tags=["quotations-admin"])

# Amendment 6b: "admin reviews all quotations and daily activity." Director-
# only, matching the Margin Performance report's own gate (K.3 restricts
# cost/margin figures to PM/Director) and the Audit Log's Director-only
# precedent -- this screen shows the same cost/margin fields Margin
# Performance already does, to every project at once, so it gets the
# stricter of the two gates rather than the broader Sales/PM/Director one
# used for a single project's own Documents screen.
ROLES = ("director",)


class QuotationSummaryOut(BaseModel):
    id: uuid.UUID
    document_no: str
    status: QuotationStatus
    project_id: uuid.UUID
    project_no: str
    client_name: str
    sports: list[str]
    cost_total: float
    selling_after_discount: float
    quotation_total: float
    margin_percent: float
    below_floor: bool
    created_at: datetime
    released_at: datetime | None
    sent_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# Amendment 12 (Section 11): "Pending Quotation" / "Old Quotation" nav
# shortcuts reuse this same screen with a preset status_group instead of
# a single status -- matching dashboard.py's own "pending" definition
# exactly (DRAFT/RELEASED/SENT), so the drill-down's row count matches
# what the Dashboard tile showed. "old" = every terminal status.
STATUS_GROUPS = {
    "pending": (QuotationStatus.DRAFT, QuotationStatus.RELEASED, QuotationStatus.SENT),
    "old": (
        QuotationStatus.WON,
        QuotationStatus.LOST,
        QuotationStatus.EXPIRED,
        QuotationStatus.SUPERSEDED,
    ),
}


def _filtered_query(
    db: Session,
    status: QuotationStatus | None,
    status_group: str | None,
    project_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
):
    """Filters by created_at -- the one timestamp every quotation carries
    regardless of status (released_at/sent_at are still null on a fresh
    Draft), so a date range here means 'created in this window' rather than
    a status-specific milestone. Reports' own Pipeline/Margin reports
    already cover the 'released in period' financial-reporting angle."""
    query = db.query(Quotation).join(Project, Quotation.project_id == Project.id).join(
        Client, Project.client_id == Client.id
    )
    if status:
        query = query.filter(Quotation.status == status)
    elif status_group in STATUS_GROUPS:
        query = query.filter(Quotation.status.in_(STATUS_GROUPS[status_group]))
    if project_id:
        query = query.filter(Quotation.project_id == project_id)
    if client_id:
        query = query.filter(Project.client_id == client_id)
    if date_from:
        query = query.filter(Quotation.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Quotation.created_at <= datetime.combine(date_to, datetime.max.time()))
    return query.order_by(Quotation.created_at.desc())


def _to_summary(db: Session, quotation: Quotation, project: Project, client: Client) -> QuotationSummaryOut:
    return QuotationSummaryOut(
        id=quotation.id,
        document_no=quotation.document_no,
        status=_effective_quotation_status(quotation),
        project_id=project.id,
        project_no=project.project_no,
        client_name=client.name,
        sports=_sports_for_quotation(db, quotation.id),
        cost_total=float(quotation.cost_total),
        selling_after_discount=float(quotation.selling_after_discount),
        quotation_total=float(quotation.quotation_total),
        margin_percent=float(quotation.margin_percent),
        below_floor=quotation.below_floor,
        created_at=quotation.created_at,
        released_at=quotation.released_at,
        sent_at=quotation.sent_at,
    )


@quotations_admin_router.get("/quotations", response_model=list[QuotationSummaryOut])
def list_all_quotations(
    status: QuotationStatus | None = None,
    status_group: str | None = None,
    project_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    rows = _filtered_query(db, status, status_group, project_id, client_id, date_from, date_to).all()
    out = []
    for q in rows:
        project = db.query(Project).filter(Project.id == q.project_id).first()
        client = db.query(Client).filter(Client.id == project.client_id).first()
        out.append(_to_summary(db, q, project, client))
    return out


@quotations_admin_router.get("/quotations/export")
def export_all_quotations(
    status: QuotationStatus | None = None,
    status_group: str | None = None,
    project_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """Amendment 6b, Director-approved scope (14 Sept 2026): the All
    Quotations screen gets its own export on top of browse-and-drill.
    CSV, matching the Audit Log export's own reasoning -- the simplest,
    most universally-openable tabular format, same filtered result set the
    screen itself is showing rather than a separate unfiltered dump. A
    per-quotation PDF already exists (GET /quotations/{id}/pdf, unaffected
    by this endpoint); this is the bulk/tabular counterpart, not a
    replacement for it."""
    rows = _filtered_query(db, status, status_group, project_id, client_id, date_from, date_to).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "document_no", "status", "project_no", "client_name", "sports",
            "cost_total", "selling_after_discount", "quotation_total", "margin_percent",
            "below_floor", "created_at", "released_at", "sent_at",
        ]
    )
    for q in rows:
        project = db.query(Project).filter(Project.id == q.project_id).first()
        client = db.query(Client).filter(Client.id == project.client_id).first()
        summary = _to_summary(db, q, project, client)
        writer.writerow(
            sanitize_row(
                [
                    summary.document_no, summary.status.value, summary.project_no, summary.client_name,
                    "; ".join(summary.sports), summary.cost_total, summary.selling_after_discount,
                    summary.quotation_total, summary.margin_percent, summary.below_floor,
                    summary.created_at.isoformat(),
                    summary.released_at.isoformat() if summary.released_at else "",
                    summary.sent_at.isoformat() if summary.sent_at else "",
                ]
            )
        )

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=all_quotations.csv"},
    )
