import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core import follow_up_sync, ownership
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.follow_up import FollowUpEntityType
from app.models.opportunity import TERMINAL_STAGES, Opportunity, OpportunityStage
from app.models.project import Project, ProjectPhase

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

# Amendment 44 (Section E step 5): same write/read role split
# ClientsAdmin.jsx's canCreateClient / GET /clients already use for the
# same kind of data.
WRITE_ROLES = ("sales", "pm", "director")
READ_ROLES = ("sales", "pm", "director", "procurement")


def _require_future_or_today(value: date) -> None:
    if value < date.today():
        raise HTTPException(status_code=400, detail="next_follow_up_date cannot be in the past")


class OpportunityCreate(BaseModel):
    lead_name: str
    lead_phone: str | None = None
    lead_email: str | None = None
    # Set only if the enquiry is already known to be an existing Client --
    # "Add Enquiry" itself never creates a Client row (see link-client).
    client_id: uuid.UUID | None = None
    next_follow_up_date: date
    # Amendment 45 (Section 51): a general free-text catch-all, distinct
    # from next_follow_up_date/follow-up note -- same role as Client.notes.
    notes: str | None = None


class OpportunityStageUpdate(BaseModel):
    stage: OpportunityStage
    # Required for every transition except to a terminal stage (WON/LOST),
    # which instead clears next_follow_up_date -- see Opportunity's own
    # docstring for why the column itself stays nullable.
    next_follow_up_date: date | None = None
    lost_reason: str | None = None


class OpportunityFollowUpUpdate(BaseModel):
    # Unlike Client's own same-named endpoint, this one cannot clear the
    # date to null -- only a WON/LOST stage change can (see Opportunity's
    # own docstring). Pushing a follow-up out is the only thing this does.
    next_follow_up_date: date
    follow_up_note: str | None = None


class OpportunityLinkClientUpdate(BaseModel):
    client_id: uuid.UUID


class OpportunityNotesUpdate(BaseModel):
    notes: str | None = None


def _clean_optional(value: str | None) -> str | None:
    """Trim; a blank string means 'clear it', same as sending null."""
    if value is None:
        return None
    value = value.strip()
    return value or None


class OpportunityDetailsUpdate(BaseModel):
    # Amendment 47 (Section 52): correcting a typo in a lead's own contact
    # details. lead_phone/lead_email are only touched when sent; sending
    # null or a blank string clears them.
    lead_name: str
    lead_phone: str | None = None
    lead_email: str | None = None


class OpportunityOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None  # Amendment 60: who owns this enquiry (None = unassigned)
    client_id: uuid.UUID | None
    lead_name: str
    lead_phone: str | None
    lead_email: str | None
    stage: OpportunityStage
    lost_reason: str | None
    next_follow_up_date: date | None
    follow_up_note: str | None
    notes: str | None
    project_id: uuid.UUID | None
    created_by_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=OpportunityOut, status_code=201)
def create_opportunity(
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Add Enquiry -- the quick-capture intake the Design input calls for,
    distinct from POST /clients: no ClientType or any other full-Client
    field is asked for here."""
    # WP5 containment: creating an Opportunity always writes a follow-up (the
    # mandatory next_follow_up_date), so it is blocked like every other route that
    # writes follow-up data -- checked first, before anything else, so a rejection
    # leaves no partial change.
    if follow_up_sync.follow_up_writes_locked(db):
        raise HTTPException(status_code=423, detail=follow_up_sync.WRITES_LOCKED_DETAIL)
    _require_future_or_today(payload.next_follow_up_date)
    if payload.client_id is not None:
        ownership.require_own_client(db, current_user, payload.client_id)
        if not db.query(Client).filter(Client.id == payload.client_id).first():
            raise HTTPException(status_code=404, detail="Client not found")

    opportunity = Opportunity(**payload.model_dump(), created_by_id=current_user.id, owner_id=current_user.id)
    db.add(opportunity)
    db.flush()  # assigns opportunity.id, which the FollowUp row below needs
    follow_up_sync.set_primary_follow_up(
        db, opportunity, FollowUpEntityType.OPPORTUNITY,
        due_date=opportunity.next_follow_up_date, note=opportunity.follow_up_note,
        current_user=current_user,
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(
    stage: OpportunityStage | None = None,
    relationship: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """relationship=lead -> client_id is null; relationship=client ->
    client_id is set. Matches the CRM reference's All/Leads/Clients tabs
    the Design input names."""
    query = db.query(Opportunity)
    if ownership.scoping_applies(db, current_user):
        query = query.filter(Opportunity.owner_id == current_user.id)
    if stage is not None:
        query = query.filter(Opportunity.stage == stage)
    if relationship == "lead":
        query = query.filter(Opportunity.client_id.is_(None))
    elif relationship == "client":
        query = query.filter(Opportunity.client_id.isnot(None))
    return query.order_by(Opportunity.created_at.desc()).all()


@router.get("/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(
    opportunity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opportunity


@router.patch("/{opportunity_id}/stage", response_model=OpportunityOut)
def update_opportunity_stage(
    opportunity_id: uuid.UUID,
    payload: OpportunityStageUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Director decision, 2026-09-22: a Lead/Opportunity can never be left
    with no future follow-up date, enforced at every stage change -- a
    transition to a non-terminal stage requires a fresh date; a transition
    to WON/LOST is terminal and clears it instead."""
    # WP5 containment: every stage change writes (or clears) a follow-up, so the whole
    # route is blocked during containment, not just the follow-up half of it -- checked
    # before the record lookup, so a rejection leaves no partial change.
    if follow_up_sync.follow_up_writes_locked(db):
        raise HTTPException(status_code=423, detail=follow_up_sync.WRITES_LOCKED_DETAIL)
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # WP6 (correction plan, 2026-09-28, tightened after review): the only route to Won is
    # Qualified -> Start Project -> Quotation marked Won (mark_quotation_won, which writes
    # Opportunity.stage directly and never calls this endpoint). This PATCH endpoint
    # unconditionally refuses a direct transition to Won -- no exception for an
    # already-Confirmed Project, deliberately: checking the Project's phase here could
    # never actually distinguish "confirmed by a real Quotation acceptance" from any other
    # way that state might arise, so it is not a safe condition to gate on. Rejecting Won
    # here outright, always, is the only version of this rule that cannot be bypassed.
    # This never touches existing historical rows (no migration, no backfill) -- it only
    # governs new stage transitions going forward, same as every other check here.
    if payload.stage == OpportunityStage.WON:
        raise HTTPException(
            status_code=409,
            detail=(
                "An Opportunity can only be marked Won by marking its Project's Quotation "
                "Won -- start a Project (it must be Qualified first) and mark its Quotation "
                "Won, rather than changing the Opportunity's stage directly."
            ),
        )

    if payload.stage in TERMINAL_STAGES:
        # WP5 integration: clearing the date also completes the shared FollowUp row
        # (see follow_up_sync.set_primary_follow_up) -- the note itself is left as
        # historical context, same as before this integration.
        follow_up_sync.set_primary_follow_up(
            db, opportunity, FollowUpEntityType.OPPORTUNITY,
            due_date=None, note=opportunity.follow_up_note, current_user=current_user,
        )
    else:
        if payload.next_follow_up_date is None:
            raise HTTPException(
                status_code=400,
                detail="next_follow_up_date is required when moving to a non-terminal stage",
            )
        _require_future_or_today(payload.next_follow_up_date)
        follow_up_sync.set_primary_follow_up(
            db, opportunity, FollowUpEntityType.OPPORTUNITY,
            due_date=payload.next_follow_up_date, note=opportunity.follow_up_note, current_user=current_user,
        )

    old_stage = opportunity.stage
    opportunity.stage = payload.stage
    opportunity.lost_reason = payload.lost_reason if payload.stage == OpportunityStage.LOST else None

    # WP6 (correction plan, 2026-09-28): a still-Pre-sales Project whose Opportunity is
    # independently marked Lost is abandoned -- kept, never deleted, simply out of the
    # active pipeline. A Project already Confirmed (its Quotation already won) is
    # untouched here; mark_quotation_won is the only place that confirms a Project, and
    # once confirmed it stays confirmed regardless of what its Opportunity does later.
    if (
        old_stage != OpportunityStage.LOST
        and payload.stage == OpportunityStage.LOST
        and opportunity.project_id is not None
    ):
        linked_project = db.query(Project).filter(Project.id == opportunity.project_id).first()
        if linked_project is not None and linked_project.phase == ProjectPhase.PRESALES:
            linked_project.phase = ProjectPhase.ABANDONED

    # WP3 (correction plan, 2026-09-27): a stage change is a significant business
    # event (especially the transition to Won/Lost, which the whole downstream
    # pipeline reads off) and was not audit-logged before this. Routine follow-up
    # note/date edits on this same record stay out of the audit log on purpose
    # (see update_opportunity_follow_up below) -- only the stage itself, which is
    # what "significant" means here, is logged.
    if old_stage != opportunity.stage:
        write_audit_log_entry(
            db, current_user, "opportunity", opportunity.id, "stage",
            old_value=old_stage.value, new_value=opportunity.stage.value,
            reason=payload.lost_reason if opportunity.stage == OpportunityStage.LOST else None,
            request=request,
        )

    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.patch("/{opportunity_id}/follow-up", response_model=OpportunityOut)
def update_opportunity_follow_up(
    opportunity_id: uuid.UUID,
    payload: OpportunityFollowUpUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Deliberately NOT audit-logged (correction-plan decision, 2026-09-27): a routine
    follow-up date/note edit is exactly the kind of noise the Director's activity feed
    should stay free of. Its own reschedule history is WP5's job (a dedicated
    FollowUpHistory table), not this endpoint calling write_audit_log_entry -- see
    update_opportunity_stage above for the one Opportunity event that IS logged."""
    # WP5 containment: see create_opportunity's own comment above.
    if follow_up_sync.follow_up_writes_locked(db):
        raise HTTPException(status_code=423, detail=follow_up_sync.WRITES_LOCKED_DETAIL)
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opportunity.stage in TERMINAL_STAGES:
        raise HTTPException(status_code=400, detail="Cannot set a follow-up date on a closed Opportunity")

    _require_future_or_today(payload.next_follow_up_date)
    follow_up_sync.set_primary_follow_up(
        db, opportunity, FollowUpEntityType.OPPORTUNITY,
        due_date=payload.next_follow_up_date, note=payload.follow_up_note, current_user=current_user,
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.patch("/{opportunity_id}/link-client", response_model=OpportunityOut)
def link_opportunity_client(
    opportunity_id: uuid.UUID,
    payload: OpportunityLinkClientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Attaches an already-existing Client -- does not create one. Creating
    a Client still goes through the existing, unchanged POST /clients."""
    ownership.require_own_client(db, current_user, payload.client_id)
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    opportunity.client_id = payload.client_id
    # Amendment 60: linking a client to an enquiry gives a client with no owner the enquiry's owner.
    if client.owner_id is None:
        client.owner_id = opportunity.owner_id
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.patch("/{opportunity_id}/details", response_model=OpportunityOut)
def update_opportunity_details(
    opportunity_id: uuid.UUID,
    payload: OpportunityDetailsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Amendment 47 (Section 52): fixes a typo in name/phone/email. Allowed
    at any stage, including Won/Lost -- it corrects a record, it is not a
    workflow step. Not audit-logged, same as follow-up/notes."""
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    lead_name = payload.lead_name.strip()
    if not lead_name:
        raise HTTPException(status_code=400, detail="lead_name cannot be blank")

    opportunity.lead_name = lead_name
    sent = payload.model_fields_set
    if "lead_phone" in sent:
        opportunity.lead_phone = _clean_optional(payload.lead_phone)
    if "lead_email" in sent:
        opportunity.lead_email = _clean_optional(payload.lead_email)
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.patch("/{opportunity_id}/notes", response_model=OpportunityOut)
def update_opportunity_notes(
    opportunity_id: uuid.UUID,
    payload: OpportunityNotesUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opportunity.notes = payload.notes
    db.commit()
    db.refresh(opportunity)
    return opportunity
