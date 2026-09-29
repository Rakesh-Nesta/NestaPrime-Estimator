"""WP5 (correction plan, 2026-09-27): resolves a FollowUp's (entity_type, entity_id) back to
the exact read/write role gate and owner_id that entity's own existing screen already uses --
the /follow-ups API never decides permission on its own. Each entry's roles are copied
verbatim from that entity's own router (cited in the comment) rather than re-derived, so this
can never drift into being more permissive than the record itself already is.

Own-records scoping (Amendment 60, app/core/ownership.py): Client, Opportunity and Project
carry owner_id directly. Every entity that instead belongs to a Project (Site Survey, Cost
Sheet, Estimate, Quotation, Work Order, and Payment Milestone via its Work Order) is scoped
by that Project's owner_id -- the same records a Sales user's /quotations, /estimates and
/projects lists are already narrowed to when the switch is on. Price Request has no owner
concept at all (Amendment 60's scoping was never extended to procurement's own screens), so
it is gated by role only.
"""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import ownership
from app.models.client import Client
from app.models.document import CostSheet, Estimate, Quotation
from app.models.follow_up import FollowUp, FollowUpEntityType, FollowUpStatus
from app.models.opportunity import Opportunity
from app.models.price_request import PriceRequest
from app.models.project import Project
from app.models.site_survey import SiteSurvey
from app.models.work_order import WorkOrder, WorkOrderPaymentMilestone


@dataclass
class ResolvedEntity:
    owner_id: uuid.UUID | None
    read_roles: tuple[str, ...]
    write_roles: tuple[str, ...]
    # True only for the three entities Amendment 60's own-records switch already covers
    # directly (Client, Opportunity, Project) or that resolve to one of their projects.
    owner_scoping_eligible: bool


def _project_owner(db: Session, project_id: uuid.UUID | None) -> uuid.UUID | None:
    if project_id is None:
        return None
    project = db.query(Project).filter(Project.id == project_id).first()
    return project.owner_id if project else None


def resolve_entity(db: Session, entity_type: FollowUpEntityType, entity_id: uuid.UUID) -> ResolvedEntity | None:
    if entity_type == FollowUpEntityType.CLIENT:
        row = db.query(Client).filter(Client.id == entity_id).first()
        if not row:
            return None
        # clients.py: create/edit follow-up = sales/pm/director; READ_ROLES adds procurement.
        return ResolvedEntity(row.owner_id, ("sales", "pm", "director", "procurement"), ("sales", "pm", "director"), True)

    if entity_type == FollowUpEntityType.OPPORTUNITY:
        row = db.query(Opportunity).filter(Opportunity.id == entity_id).first()
        if not row:
            return None
        # opportunities.py: WRITE_ROLES / READ_ROLES.
        return ResolvedEntity(row.owner_id, ("sales", "pm", "director", "procurement"), ("sales", "pm", "director"), True)

    if entity_type == FollowUpEntityType.PROJECT:
        row = db.query(Project).filter(Project.id == entity_id).first()
        if not row:
            return None
        # projects.py: create = sales/pm/director; LIST_ROLES adds procurement/site_engineer/ca_tax.
        return ResolvedEntity(
            row.owner_id,
            ("sales", "pm", "director", "procurement", "site_engineer", "ca_tax"),
            ("sales", "pm", "director"),
            True,
        )

    if entity_type == FollowUpEntityType.SITE_SURVEY:
        row = db.query(SiteSurvey).filter(SiteSurvey.id == entity_id).first()
        if not row:
            return None
        # site_surveys.py: ROLES = site_engineer/pm/director for both read and write.
        return ResolvedEntity(_project_owner(db, row.project_id), ("site_engineer", "pm", "director"), ("site_engineer", "pm", "director"), True)

    if entity_type == FollowUpEntityType.COST_SHEET:
        row = db.query(CostSheet).filter(CostSheet.id == entity_id).first()
        if not row:
            return None
        # documents.py: COST_ROLES write; read additionally allows Sales (K.3 rate-blind, cost stripped elsewhere).
        return ResolvedEntity(_project_owner(db, row.project_id), ("sales", "pm", "director"), ("pm", "director"), True)

    if entity_type == FollowUpEntityType.ESTIMATE:
        row = db.query(Estimate).filter(Estimate.id == entity_id).first()
        if not row:
            return None
        # documents.py: DOCUMENT_ROLES for list/get/send.
        return ResolvedEntity(_project_owner(db, row.project_id), ("sales", "pm", "director"), ("sales", "pm", "director"), True)

    if entity_type == FollowUpEntityType.QUOTATION:
        row = db.query(Quotation).filter(Quotation.id == entity_id).first()
        if not row:
            return None
        return ResolvedEntity(_project_owner(db, row.project_id), ("sales", "pm", "director"), ("sales", "pm", "director"), True)

    if entity_type == FollowUpEntityType.PRICE_REQUEST:
        row = db.query(PriceRequest).filter(PriceRequest.id == entity_id).first()
        if not row:
            return None
        # price_requests.py: READ_ROLES == WRITE_ROLES == pm/director/procurement. No owner concept.
        return ResolvedEntity(None, ("pm", "director", "procurement"), ("pm", "director", "procurement"), False)

    if entity_type == FollowUpEntityType.WORK_ORDER:
        row = db.query(WorkOrder).filter(WorkOrder.id == entity_id).first()
        if not row:
            return None
        # work_orders.py: ROLES write pm/director; READ_ROLES adds ca_tax.
        return ResolvedEntity(_project_owner(db, row.project_id), ("pm", "director", "ca_tax"), ("pm", "director"), True)

    if entity_type == FollowUpEntityType.PAYMENT_MILESTONE:
        row = db.query(WorkOrderPaymentMilestone).filter(WorkOrderPaymentMilestone.id == entity_id).first()
        if not row:
            return None
        wo = db.query(WorkOrder).filter(WorkOrder.id == row.work_order_id).first()
        return ResolvedEntity(_project_owner(db, wo.project_id) if wo else None, ("pm", "director", "ca_tax"), ("pm", "director"), True)

    return None


def check_follow_up_access(
    db: Session, current_user, entity_type: FollowUpEntityType, entity_id: uuid.UUID, need: str
) -> ResolvedEntity:
    """need is "read" or "write". Raises 404 the same way enforce_own_records does for a
    Sales user outside the own-records switch's reach -- never a 403 that would confirm the
    record exists -- and a plain 404 when the record itself doesn't exist at all."""
    resolved = resolve_entity(db, entity_type, entity_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"{entity_type.value.replace('_', ' ').title()} not found")

    roles = resolved.write_roles if need == "write" else resolved.read_roles
    if current_user.role.value not in roles:
        raise HTTPException(status_code=403, detail="Not permitted for this role")

    if (
        resolved.owner_scoping_eligible
        and current_user.role.value == "sales"
        and ownership.scoping_applies(db, current_user)
        and resolved.owner_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail=f"{entity_type.value.replace('_', ' ').title()} not found")

    return resolved


def visible_follow_ups(
    db: Session, viewing_user, *, owner_id: uuid.UUID | None = None, status: FollowUpStatus | None = None
) -> list[FollowUp]:
    """The single "which FollowUp rows can viewing_user actually see" rule, shared between GET
    /follow-ups' own org-wide and owner-scoped listings (follow_ups.py::list_follow_ups) and the
    dashboard's followups_due_count (correction plan, 2026-09-29) -- extracted so the two can
    never independently drift out of agreement again, the way followups_due_count's earlier,
    separate Client/Opportunity-column-based computation once did.

    With owner_id given, narrows to that owner's rows outright ("my follow-ups"). Otherwise, a
    Sales viewer is always narrowed to their own rows -- unconditionally, regardless of the
    Amendment 60 own-records switch, the same rule list_follow_ups has enforced since WP5 --
    and every other role sees the full candidate set. Either way, every surviving row is then
    re-checked individually via check_follow_up_access: a row's owner_id and its entity's own
    current access gate can diverge (an explicitly assigned specialist, or a parent reassigned
    away from whoever the row still names), so passing the owner/role filter above is necessary
    but never sufficient on its own."""
    query = db.query(FollowUp)
    if owner_id is not None:
        query = query.filter(FollowUp.owner_id == owner_id)
    elif viewing_user.role.value == "sales":
        query = query.filter(FollowUp.owner_id == viewing_user.id)
    if status is not None:
        query = query.filter(FollowUp.status == status)
    rows = query.order_by(FollowUp.due_date.asc()).all()

    visible = []
    for row in rows:
        try:
            check_follow_up_access(db, viewing_user, row.entity_type, row.entity_id, need="read")
        except HTTPException:
            continue
        visible.append(row)
    return visible
