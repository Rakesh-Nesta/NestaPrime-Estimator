"""Project Overview (correction plan Part 4, 2026-09-28): one screen per Project answering
"what's the state of this deal right now" without visiting six different screens. Built
entirely from data that already exists elsewhere (WP3 audit log, WP5 shared follow-ups, WP6
phase, WP7 readiness, Amendment 50 payments) -- no new business logic, no new source of truth,
and "access to this screen is enforced exactly like the record's own screen": each section is
gated by that exact same section's own existing role list, never a looser one invented here.

Vendor/price-request blockers are explicitly NOT computed: PriceRequest has no project_id, and
no other column chains it back to a specific project (PriceRequestItem.rate_item_id points at
the shared rate-master catalog, used across many projects' Cost Sheets; a confirmed
VendorReply's "applied as cost_sheet_line" doesn't record which line). Inferring a link or
showing every open request regardless of project would be actively misleading, not merely
incomplete -- so this is surfaced as an explicit "unavailable, pending a linking decision"
placeholder rather than silently omitted or guessed at."""
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core import ownership
from app.core.auth import require_roles
from app.core.follow_up_entities import resolve_entity
from app.core.readiness import check_client_identity, compute_waivable_checks
from app.db.session import get_db
from app.models.audit_log import AuditLogEntry
from app.models.client import Client
from app.models.document import (
    CostSheet,
    CostSheetStatus,
    Estimate,
    EstimateOption,
    EstimateOptionClientStatus,
    EstimateStatus,
    Quotation,
    QuotationStatus,
)
from app.models.follow_up import FollowUp, FollowUpEntityType, FollowUpStatus, TERMINAL_FOLLOW_UP_STATUSES
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.readiness_exception import ReadinessDocumentType, ReadinessException, ReadinessExceptionStatus
from app.models.skip_request import SkipRequest, SkipRequestStatus
from app.models.user import User
from app.models.work_order import WorkOrder
from app.services import payments as payments_service

project_overview_router = APIRouter(tags=["project-overview"])

# Matches FollowUpEntityType.PROJECT's own read_roles (app/core/follow_up_entities.py) and
# projects.py's own LIST_ROLES -- the same set of roles that can already open this project at
# all, so this endpoint's own top-level gate adds no new exposure. Individual sections below
# are gated more narrowly, to each one's own existing source endpoint's role list -- a
# procurement/site_engineer/ca_tax viewer reaches this screen but sees a sparser one, exactly
# matching what they could already see on the underlying screens.
OVERVIEW_ROLES = ("sales", "pm", "director", "procurement", "site_engineer", "ca_tax")
# documents.py's own DOCUMENT_ROLES (list_estimates/list_quotations) -- narrower than
# OVERVIEW_ROLES above -- gates the Cost Sheet/Estimate/Quotation/readiness-exception pending
# items, since those describe state a procurement/site_engineer/ca_tax viewer can't otherwise
# see on the Documents screen itself.
DOCUMENT_CHAIN_ROLES = ("sales", "pm", "director")
# app/api/readiness.py's own VIEW_ROLES -- unchanged, reused verbatim.
READINESS_VIEW_ROLES = ("sales", "pm", "director")
# app/api/dashboard.py's own PAYMENTS_ROLES -- unchanged, reused verbatim.
PAYMENT_VIEW_ROLES = ("pm", "director", "ca_tax")
# app/api/audit_log.py's own ROLES -- unchanged, reused verbatim. Narrower than the rest of
# this screen on purpose: nothing here may show a PM/Sales user something the Audit Log
# screen itself would refuse them.
ACTIVITY_VIEW_ROLES = ("director", "admin")

_ACTIVITY_DOCUMENT_TYPES = (
    "project", "opportunity", "cost_sheet", "estimate", "quotation", "skip_request", "site_survey",
)


def _is_past(moment: datetime | None) -> bool:
    """Same pattern as documents.py's own _is_past: expires_at is typed `date | None` but
    stored as a plain (timezone-naive) DateTime -- compare against a same-awareness `now`
    rather than assume either representation."""
    if moment is None:
        return False
    now = datetime.now(UTC)
    if moment.tzinfo is None:
        now = now.replace(tzinfo=None)
    return now > moment


class PendingItemOut(BaseModel):
    source: str
    label: str
    waiting_on: str  # "us" | "client" | "vendor"
    due_date: date | None
    screen: str  # frontend screen key: "documents" | "scope" | "site_survey" | "follow_ups"
    document_id: uuid.UUID | None = None


class ReadinessCheckSummaryOut(BaseModel):
    key: str
    label: str
    passed: bool
    waivable: bool
    pending_exception: bool


class ReadinessGapsOut(BaseModel):
    client_identity_passed: bool
    client_identity_missing: list[str]
    checks: list[ReadinessCheckSummaryOut]


class PaymentBlockerOut(BaseModel):
    work_order_id: uuid.UUID
    work_order_status: str
    order_value: float
    total_received: float
    outstanding: float
    overdue: bool
    overdue_amount: float
    next_due_date: date | None


class VendorPriceRequestBlockersOut(BaseModel):
    available: bool
    reason: str | None
    items: list = []


class ActivityEntryOut(BaseModel):
    timestamp: datetime
    document_type: str
    field: str
    old_value: str | None
    new_value: str | None
    reason: str | None
    user_name: str

    model_config = ConfigDict(from_attributes=True)


class ProjectOverviewOut(BaseModel):
    project_id: uuid.UUID
    project_no: str
    city: str
    phase: str
    client_id: uuid.UUID
    client_name: str
    owner_id: uuid.UUID | None
    owner_name: str | None
    opportunity_id: uuid.UUID | None
    opportunity_stage: str | None

    pending_items: list[PendingItemOut]
    document_chain_visible: bool

    readiness_visible: bool
    readiness: ReadinessGapsOut | None

    payment_visible: bool
    payment_blocker: PaymentBlockerOut | None

    vendor_price_requests: VendorPriceRequestBlockersOut

    activity_visible: bool
    latest_activity: list[ActivityEntryOut]


def _cost_sheet_pending_item(db: Session, project: Project) -> tuple[PendingItemOut | None, CostSheet | None]:
    sheets = db.query(CostSheet).filter(CostSheet.project_id == project.id).all()
    active = next((c for c in sheets if c.status != CostSheetStatus.SUPERSEDED), None)
    if not active:
        pending_skip = (
            db.query(SkipRequest)
            .filter(SkipRequest.project_id == project.id, SkipRequest.status == SkipRequestStatus.PENDING)
            .first()
        )
        if pending_skip:
            return (
                PendingItemOut(
                    source="skip_request", label="Skip requested -- awaiting PM/Director approval",
                    waiting_on="us", due_date=None, screen="documents",
                ),
                None,
            )
        return (
            PendingItemOut(
                source="cost_sheet", label="Awaiting PM/Director to build the Cost Sheet",
                waiting_on="us", due_date=None, screen="documents",
            ),
            None,
        )
    if active.status in (CostSheetStatus.DRAFT, CostSheetStatus.UNVERIFIED):
        label = (
            "Cost Sheet awaiting PM/Director verification" if active.status == CostSheetStatus.DRAFT
            else "Skip-generated Cost Sheet awaiting PM/Director verification"
        )
        return (
            PendingItemOut(source="cost_sheet", label=label, waiting_on="us", due_date=None, screen="documents"),
            active,
        )
    return None, active


def _options_by_estimate(db: Session, estimate_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[EstimateOption]]:
    """EstimateOption has no ORM relationship back to Estimate anywhere in this codebase --
    every other call site queries it directly by estimate_id (see app/api/documents.py) --
    so this batches that same query for a set of estimates rather than one-per-estimate."""
    if not estimate_ids:
        return {}
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id.in_(estimate_ids)).all()
    by_estimate: dict[uuid.UUID, list[EstimateOption]] = {}
    for o in options:
        by_estimate.setdefault(o.estimate_id, []).append(o)
    return by_estimate


def _estimate_pending_item(db: Session, project: Project, active_cost_sheet: CostSheet | None) -> tuple[PendingItemOut | None, list[Estimate]]:
    estimates = db.query(Estimate).filter(Estimate.project_id == project.id).all()
    live = [e for e in estimates if e.status != EstimateStatus.SUPERSEDED]
    if not live:
        if active_cost_sheet is not None and active_cost_sheet.status in (CostSheetStatus.VERIFIED, CostSheetStatus.UNVERIFIED):
            return (
                PendingItemOut(source="estimate", label="Awaiting PM/Director to create the Estimate", waiting_on="us", due_date=None, screen="documents"),
                live,
            )
        return None, live

    options_by_estimate = _options_by_estimate(db, [e.id for e in live])
    for e in live:
        effective_status = e.status
        if e.status == EstimateStatus.SENT and _is_past(e.expires_at):
            effective_status = EstimateStatus.EXPIRED
        options = options_by_estimate.get(e.id, [])
        if any(o.client_status in (EstimateOptionClientStatus.APPROVED, EstimateOptionClientStatus.DEMAND_RECEIVED) for o in options):
            continue  # ready for a Quotation -- not a blocker on this Estimate itself
        if effective_status == EstimateStatus.SENT:
            return (
                PendingItemOut(source="estimate", label="Awaiting client response on the Estimate", waiting_on="client", due_date=e.expires_at.date() if e.expires_at else None, screen="documents", document_id=e.id),
                live,
            )
        if effective_status == EstimateStatus.DRAFT:
            return (
                PendingItemOut(source="estimate", label="Estimate awaiting send to client", waiting_on="us", due_date=None, screen="documents", document_id=e.id),
                live,
            )
    if all((e.status == EstimateStatus.SENT and _is_past(e.expires_at)) or e.status == EstimateStatus.EXPIRED for e in live):
        return (
            PendingItemOut(source="estimate", label="Estimate expired -- a new one is needed", waiting_on="us", due_date=None, screen="documents"),
            live,
        )
    return None, live


def _quotation_release_label(q: Quotation, role: str) -> str:
    """K.3: below_floor is stripped from a Sales user's own QuotationOut (documents.py's
    _quotation_to_out) -- this label must not leak it back in plain text. cost_basis_unverified
    is NOT stripped (it's about Cost Sheet verification, not the discount/margin itself), so it
    stays nameable for every role."""
    needs_director = q.below_floor or q.cost_basis_unverified
    if not needs_director:
        return "Quotation awaiting release"
    if role == "sales":
        return "Quotation awaiting Director release"
    reasons = []
    if q.cost_basis_unverified:
        reasons.append("unverified cost basis")
    if q.below_floor:
        reasons.append("below floor")
    return f"Quotation awaiting Director release ({' / '.join(reasons)})"


def _quotation_pending_item(db: Session, project: Project, live_estimates: list[Estimate], role: str) -> tuple[PendingItemOut | None, list[Quotation]]:
    quotations = db.query(Quotation).filter(Quotation.project_id == project.id).all()
    live = [q for q in quotations if q.status != QuotationStatus.SUPERSEDED]
    if not live:
        options_by_estimate = _options_by_estimate(db, [e.id for e in live_estimates])
        has_approved_option = any(
            o.client_status in (EstimateOptionClientStatus.APPROVED, EstimateOptionClientStatus.DEMAND_RECEIVED)
            for e in live_estimates for o in options_by_estimate.get(e.id, [])
        )
        if has_approved_option:
            return PendingItemOut(source="quotation", label="Awaiting PM/Director to create the Quotation", waiting_on="us", due_date=None, screen="documents"), live
        return None, live
    for q in live:
        if q.status == QuotationStatus.WON:
            continue
        effective_status = q.status
        if q.status == QuotationStatus.SENT and _is_past(q.expires_at):
            effective_status = QuotationStatus.EXPIRED
        if effective_status == QuotationStatus.SENT:
            return PendingItemOut(source="quotation", label="Awaiting client decision on the Quotation", waiting_on="client", due_date=q.expires_at.date() if q.expires_at else None, screen="documents", document_id=q.id), live
        if effective_status == QuotationStatus.RELEASED:
            # Already past the below-floor/unverified Director gate (release_quotation enforces
            # it before a Quotation can reach Released) -- never re-mention it here.
            return PendingItemOut(source="quotation", label="Quotation ready to send to client", waiting_on="us", due_date=None, screen="documents", document_id=q.id), live
        if effective_status == QuotationStatus.DRAFT:
            return PendingItemOut(source="quotation", label=_quotation_release_label(q, role), waiting_on="us", due_date=None, screen="documents", document_id=q.id), live
    if all(q.status == QuotationStatus.LOST for q in live):
        return PendingItemOut(source="quotation", label="Quotation lost -- a new one can be raised to re-bid", waiting_on="us", due_date=None, screen="documents"), live
    return None, live


def _pending_readiness_exceptions(
    db: Session, live_estimates: list[Estimate], live_quotations: list[Quotation]
) -> list[PendingItemOut]:
    by_type_ids = [
        (ReadinessDocumentType.ESTIMATE, [e.id for e in live_estimates]),
        (ReadinessDocumentType.QUOTATION, [q.id for q in live_quotations]),
    ]
    items: list[PendingItemOut] = []
    for doc_type, ids in by_type_ids:
        if not ids:
            continue
        pending = (
            db.query(ReadinessException)
            .filter(
                ReadinessException.document_type == doc_type,
                ReadinessException.document_id.in_(ids),
                ReadinessException.status == ReadinessExceptionStatus.REQUESTED,
            )
            .all()
        )
        items.extend(
            PendingItemOut(
                source="readiness_exception",
                label=f"Readiness exception request ({rx.check_key.value.replace('_', ' ')}) awaiting Director approval",
                waiting_on="us", due_date=None, screen="documents", document_id=rx.document_id,
            )
            for rx in pending
        )
    return items


def _follow_up_pending_items(db: Session, project: Project, opportunity: Opportunity | None, current_user) -> list[PendingItemOut]:
    """Access matches check_follow_up_access in app/core/follow_up_entities.py exactly (the
    single source of truth /follow-ups itself defers to): each entity_type's own read_roles
    decides whether this viewer's role may see that entity's follow-ups at all, and Amendment
    60's own-records switch additionally scopes a Sales viewer to entities they own -- e.g. a
    site_engineer can reach this screen but must not see the linked Opportunity's or Client's
    follow-ups, only the Project's own; a Sales viewer under the own-records switch must not
    see a linked Opportunity's/Client's follow-ups when that Opportunity/Client has a
    different owner than the Project itself."""
    entity_pairs = [(FollowUpEntityType.PROJECT, project.id)]
    if opportunity is not None:
        entity_pairs.append((FollowUpEntityType.OPPORTUNITY, opportunity.id))
    if project.client_id is not None:
        entity_pairs.append((FollowUpEntityType.CLIENT, project.client_id))

    rows: list[FollowUp] = []
    for entity_type, entity_id in entity_pairs:
        resolved = resolve_entity(db, entity_type, entity_id)
        if resolved is None or current_user.role.value not in resolved.read_roles:
            continue
        if (
            resolved.owner_scoping_eligible
            and current_user.role.value == "sales"
            and ownership.scoping_applies(db, current_user)
            and resolved.owner_id != current_user.id
        ):
            continue
        rows.extend(
            db.query(FollowUp)
            .filter(FollowUp.entity_type == entity_type, FollowUp.entity_id == entity_id)
            .filter(FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES))
            .all()
        )
    items = []
    for row in sorted(rows, key=lambda r: r.due_date):
        # waiting_party is only required (and meaningful) when status == WAITING
        # (app/api/follow_ups.py's update_follow_up enforces that on the way IN, but doesn't
        # clear it on the way back out) -- a stale value from an earlier WAITING period must
        # not be trusted once the row has moved to open/in_progress.
        waiting_on = row.waiting_party.value if (row.status == FollowUpStatus.WAITING and row.waiting_party is not None) else "us"
        items.append(
            PendingItemOut(
                source="follow_up", label=row.next_action, waiting_on=waiting_on,
                due_date=row.due_date, screen="follow_ups", document_id=row.id,
            )
        )
    return items


def _readiness_gaps(db: Session, project: Project, client: Client | None) -> ReadinessGapsOut:
    identity = check_client_identity(client)
    # No specific document in view on this screen -- document_id=None previews the checks the
    # same way readiness.py's own GET /projects/{id}/readiness does before any Estimate/
    # Quotation exists yet; document_type is unused by compute_waivable_checks in that mode.
    checks = compute_waivable_checks(db, project, ReadinessDocumentType.ESTIMATE, None)
    return ReadinessGapsOut(
        client_identity_passed=identity.passed,
        client_identity_missing=identity.missing,
        checks=[
            ReadinessCheckSummaryOut(
                key=c.key, label=c.label, passed=c.passed, waivable=c.waivable,
                pending_exception=c.exception is not None and c.exception.status == ReadinessExceptionStatus.REQUESTED,
            )
            for c in checks
        ],
    )


def _payment_blocker(db: Session, project: Project, today: date) -> PaymentBlockerOut | None:
    work_order_ids = [wo.id for wo in db.query(WorkOrder.id).filter(WorkOrder.project_id == project.id).all()]
    if not work_order_ids:
        return None
    rows = payments_service.build_rows(db, today, work_order_ids=work_order_ids)
    overdue_rows = [r for r in rows if r["overdue"]]
    if not overdue_rows:
        return None
    row = max(overdue_rows, key=lambda r: r["overdue_amount"])
    return PaymentBlockerOut(
        work_order_id=row["work_order_id"], work_order_status=row["work_order_status"].value,
        order_value=row["order_value"], total_received=row["total_received"], outstanding=row["outstanding"],
        overdue=row["overdue"], overdue_amount=row["overdue_amount"], next_due_date=row["next_due_date"],
    )


def _latest_activity(db: Session, project: Project, opportunity: Opportunity | None) -> list[ActivityEntryOut]:
    doc_ids: list[uuid.UUID] = [project.id]
    if opportunity is not None:
        doc_ids.append(opportunity.id)
    doc_ids.extend(r.id for r in db.query(CostSheet.id).filter(CostSheet.project_id == project.id).all())
    doc_ids.extend(r.id for r in db.query(Estimate.id).filter(Estimate.project_id == project.id).all())
    doc_ids.extend(r.id for r in db.query(Quotation.id).filter(Quotation.project_id == project.id).all())
    doc_ids.extend(r.id for r in db.query(SkipRequest.id).filter(SkipRequest.project_id == project.id).all())

    entries = (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.document_type.in_(_ACTIVITY_DOCUMENT_TYPES), AuditLogEntry.document_id.in_(doc_ids))
        .order_by(AuditLogEntry.timestamp.desc())
        .limit(10)
        .all()
    )
    user_ids = {e.user_id for e in entries}
    users_by_id = {u.id: u.name for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return [
        ActivityEntryOut(
            timestamp=e.timestamp, document_type=e.document_type, field=e.field,
            old_value=e.old_value, new_value=e.new_value, reason=e.reason,
            user_name=users_by_id.get(e.user_id, "Unknown"),
        )
        for e in entries
    ]


@project_overview_router.get("/projects/{project_id}/overview", response_model=ProjectOverviewOut)
def get_project_overview(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OVERVIEW_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = db.query(Client).filter(Client.id == project.client_id).first()
    owner = db.query(User).filter(User.id == project.owner_id).first() if project.owner_id else None
    opportunity = db.query(Opportunity).filter(Opportunity.id == project.opportunity_id).first() if project.opportunity_id else None

    document_chain_visible = current_user.role.value in DOCUMENT_CHAIN_ROLES
    pending_items: list[PendingItemOut] = []
    if document_chain_visible:
        cost_sheet_item, active_cost_sheet = _cost_sheet_pending_item(db, project)
        if cost_sheet_item:
            pending_items.append(cost_sheet_item)
        estimate_item, live_estimates = _estimate_pending_item(db, project, active_cost_sheet)
        if estimate_item:
            pending_items.append(estimate_item)
        quotation_item, live_quotations = _quotation_pending_item(db, project, live_estimates, current_user.role.value)
        if quotation_item:
            pending_items.append(quotation_item)
        pending_items.extend(_pending_readiness_exceptions(db, live_estimates, live_quotations))
    pending_items.extend(_follow_up_pending_items(db, project, opportunity, current_user))

    readiness_visible = current_user.role.value in READINESS_VIEW_ROLES
    readiness = _readiness_gaps(db, project, client) if readiness_visible else None

    payment_visible = current_user.role.value in PAYMENT_VIEW_ROLES
    payment_blocker = _payment_blocker(db, project, datetime.now().date()) if payment_visible else None

    activity_visible = current_user.role.value in ACTIVITY_VIEW_ROLES
    latest_activity = _latest_activity(db, project, opportunity) if activity_visible else []

    return ProjectOverviewOut(
        project_id=project.id, project_no=project.project_no, city=project.city, phase=project.phase.value,
        client_id=project.client_id, client_name=client.name if client else "",
        owner_id=project.owner_id, owner_name=owner.name if owner else None,
        opportunity_id=project.opportunity_id, opportunity_stage=opportunity.stage.value if opportunity else None,
        pending_items=pending_items, document_chain_visible=document_chain_visible,
        readiness_visible=readiness_visible, readiness=readiness,
        payment_visible=payment_visible, payment_blocker=payment_blocker,
        vendor_price_requests=VendorPriceRequestBlockersOut(
            available=False,
            reason=(
                "Price requests aren't linked to a specific project in the current schema "
                "(PriceRequestItem references the shared rate-master catalog, used across many "
                "projects' Cost Sheets) -- showing them here would need a linking decision first."
            ),
        ),
        activity_visible=activity_visible, latest_activity=latest_activity,
    )
