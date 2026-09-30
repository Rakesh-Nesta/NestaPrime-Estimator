import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.clients import READ_ROLES
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.client_contact import ClientContact

router = APIRouter(prefix="/clients/{client_id}/contacts", tags=["client-contacts"])

# P2 (Client 360 contract): same write-role set as every other Client write -- ownership
# scoping is inherited for free from the global enforce_own_records dependency, since
# client_id (already a covered path param) names every route below.
WRITE_ROLES = ("sales", "pm", "director")


class ClientContactCreate(BaseModel):
    name: str
    designation: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class ClientContactUpdate(BaseModel):
    name: str | None = None
    designation: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ClientContactOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    designation: str | None
    phone: str | None
    email: str | None
    notes: str | None
    is_active: bool
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _get_client_or_404(db: Session, client_id: uuid.UUID) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _get_contact_or_404(db: Session, client_id: uuid.UUID, contact_id: uuid.UUID) -> ClientContact:
    """P2 (Client 360 contract), nested-record validation: a Contact fetched here must belong to
    the client_id named in THIS URL, independent of Amendment 60 scoping -- owning or being
    scoped to Client A must never be enough on its own to reach a Contact whose own client_id is
    actually Client B, just because A's id and B's contact id were paired in the same request.
    Rejected the same way a missing record is rejected (404), same concealed-record discipline."""
    contact = db.query(ClientContact).filter(ClientContact.id == contact_id).first()
    if contact is None or contact.client_id != client_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("", response_model=ClientContactOut, status_code=201)
def create_contact(
    client_id: uuid.UUID,
    payload: ClientContactCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    _get_client_or_404(db, client_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be blank")
    contact = ClientContact(
        client_id=client_id,
        name=name,
        designation=payload.designation,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
        created_by_id=current_user.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("", response_model=list[ClientContactOut])
def list_contacts(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    _get_client_or_404(db, client_id)
    return (
        db.query(ClientContact)
        .filter(ClientContact.client_id == client_id)
        .order_by(ClientContact.created_at.desc())
        .all()
    )


@router.patch("/{contact_id}", response_model=ClientContactOut)
def update_contact(
    client_id: uuid.UUID,
    contact_id: uuid.UUID,
    payload: ClientContactUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    contact = _get_contact_or_404(db, client_id, contact_id)
    sent = payload.model_fields_set
    if "name" in sent:
        name = (payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be blank")
        contact.name = name
    for field in ("designation", "phone", "email", "notes"):
        if field in sent:
            setattr(contact, field, getattr(payload, field))
    if "is_active" in sent and payload.is_active is not None:
        contact.is_active = payload.is_active
    db.commit()
    db.refresh(contact)
    return contact
