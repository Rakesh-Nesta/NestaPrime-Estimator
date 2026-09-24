import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.opportunity import TERMINAL_STAGES, Opportunity, OpportunityStage

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
    _require_future_or_today(payload.next_follow_up_date)
    if payload.client_id is not None:
        if not db.query(Client).filter(Client.id == payload.client_id).first():
            raise HTTPException(status_code=404, detail="Client not found")

    opportunity = Opportunity(**payload.model_dump(), created_by_id=current_user.id)
    db.add(opportunity)
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
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Director decision, 2026-09-22: a Lead/Opportunity can never be left
    with no future follow-up date, enforced at every stage change -- a
    transition to a non-terminal stage requires a fresh date; a transition
    to WON/LOST is terminal and clears it instead."""
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if payload.stage in TERMINAL_STAGES:
        opportunity.next_follow_up_date = None
    else:
        if payload.next_follow_up_date is None:
            raise HTTPException(
                status_code=400,
                detail="next_follow_up_date is required when moving to a non-terminal stage",
            )
        _require_future_or_today(payload.next_follow_up_date)
        opportunity.next_follow_up_date = payload.next_follow_up_date

    opportunity.stage = payload.stage
    opportunity.lost_reason = payload.lost_reason if payload.stage == OpportunityStage.LOST else None
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
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opportunity.stage in TERMINAL_STAGES:
        raise HTTPException(status_code=400, detail="Cannot set a follow-up date on a closed Opportunity")

    _require_future_or_today(payload.next_follow_up_date)
    opportunity.next_follow_up_date = payload.next_follow_up_date
    opportunity.follow_up_note = payload.follow_up_note
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
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    opportunity.client_id = payload.client_id
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
