import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.client_signatory import ClientSignatory

client_signatories_router = APIRouter(prefix="/clients/{client_id}/signatories", tags=["client-signatories"])

# Mirrors clients.py's own role split: Sales/PM/Director create and edit
# (signatories are entered by whoever is running the deal), Procurement
# only ever needs to read them (e.g. to confirm a PO recipient).
WRITE_ROLES = ("sales", "pm", "director")
READ_ROLES = ("sales", "pm", "director", "procurement")


def _get_client_or_404(db: Session, client_id: uuid.UUID) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _get_signatory_or_404(db: Session, client_id: uuid.UUID, signatory_id: uuid.UUID) -> ClientSignatory:
    signatory = (
        db.query(ClientSignatory)
        .filter(ClientSignatory.id == signatory_id, ClientSignatory.client_id == client_id)
        .first()
    )
    if not signatory:
        raise HTTPException(status_code=404, detail="Signatory not found")
    return signatory


class ClientSignatoryCreate(BaseModel):
    name: str
    designation: str
    email: str | None = None
    phone: str | None = None
    authorization_date: date
    authorization_doc_attachment_id: uuid.UUID | None = None
    expiry_date: date | None = None


class ClientSignatoryUpdate(BaseModel):
    name: str | None = None
    designation: str | None = None
    email: str | None = None
    phone: str | None = None
    authorization_date: date | None = None
    authorization_doc_attachment_id: uuid.UUID | None = None
    expiry_date: date | None = None
    is_active: bool | None = None


class ClientSignatoryOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    designation: str
    email: str | None
    phone: str | None
    authorization_date: date
    authorization_doc_attachment_id: uuid.UUID | None
    expiry_date: date | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@client_signatories_router.post("", response_model=ClientSignatoryOut, status_code=201)
def create_signatory(
    client_id: uuid.UUID,
    payload: ClientSignatoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Part O CLIENT_SIGNATORIES: 'signatory_id, client_id, name,
    designation, email, phone, authorization_date, authorization_doc,
    expiry_date, is_active.'"""
    _get_client_or_404(db, client_id)
    signatory = ClientSignatory(client_id=client_id, **payload.model_dump())
    db.add(signatory)
    db.commit()
    db.refresh(signatory)
    return signatory


@client_signatories_router.get("", response_model=list[ClientSignatoryOut])
def list_signatories(
    client_id: uuid.UUID,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    _get_client_or_404(db, client_id)
    query = db.query(ClientSignatory).filter(ClientSignatory.client_id == client_id)
    if not include_inactive:
        query = query.filter(ClientSignatory.is_active.is_(True))
    return query.order_by(ClientSignatory.name).all()


@client_signatories_router.patch("/{signatory_id}", response_model=ClientSignatoryOut)
def update_signatory(
    client_id: uuid.UUID,
    signatory_id: uuid.UUID,
    payload: ClientSignatoryUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Deactivation (is_active=False) is the intended way to revoke a
    signatory -- rows are never deleted, matching this app's write-once/
    supersede convention for approval-adjacent records (Attachments)."""
    _get_client_or_404(db, client_id)
    signatory = _get_signatory_or_404(db, client_id, signatory_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(signatory, field, value)
    db.commit()
    db.refresh(signatory)
    return signatory
