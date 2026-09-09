import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client, ClientType

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientCreate(BaseModel):
    name: str
    type: ClientType
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    billing_address: str | None = None
    gstin: str | None = None
    pan: str | None = None
    # M.7.2 rule 5: WhatsApp defaults opted-out (Meta requires affirmative
    # opt-in); ordinary business email is opt-out by nature, so it
    # defaults opted-in -- same convention as Vendor's own consent fields.
    whatsapp_opt_in: bool = False
    email_opt_in: bool = True
    consent_date: date | None = None


class ClientFlagsUpdate(BaseModel):
    overdue_flag: bool | None = None
    blacklist_flag: bool | None = None


class ClientConsentUpdate(BaseModel):
    whatsapp_opt_in: bool | None = None
    email_opt_in: bool | None = None
    consent_date: date | None = None


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    type: ClientType
    contact_name: str | None
    phone: str | None
    email: str | None
    overdue_flag: bool
    blacklist_flag: bool
    whatsapp_opt_in: bool
    email_opt_in: bool
    consent_date: date | None

    model_config = ConfigDict(from_attributes=True)


# Client creation isn't itemised in M.4's matrix, but it's the natural
# extension of "create cost sheet / estimate / quotation" — Sales is where
# leads enter the system, so Sales/PM/Director all create clients.
@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director", "procurement")),
):
    return db.query(Client).order_by(Client.name).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director", "procurement")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientOut)
def update_client_flags(
    client_id: uuid.UUID,
    payload: ClientFlagsUpdate,
    db: Session = Depends(get_db),
    # Part O: "overdue_flag (blocks new Quotation release until Director
    # clears), blacklist_flag (blocks new Estimates)" -- Director-only,
    # since only a Director is named as able to set or clear either.
    current_user=Depends(require_roles("director")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.overdue_flag is not None:
        client.overdue_flag = payload.overdue_flag
    if payload.blacklist_flag is not None:
        client.blacklist_flag = payload.blacklist_flag

    db.commit()
    db.refresh(client)
    return client


@router.patch("/{client_id}/consent", response_model=ClientOut)
def update_client_consent(
    client_id: uuid.UUID,
    payload: ClientConsentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    # M.7.2 rule 5: recording what a specific client told us about
    # consent is ordinary client-relationship upkeep (same role gate as
    # creating the client), distinct from the Director-only "manage
    # ... consent settings" row in M.7.5's rights table, which is about
    # the global consent-default policy (Q.1), not one client's own
    # recorded answer.
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        old_value = getattr(client, field)
        if old_value != value:
            write_audit_log_entry(
                db, current_user, "client", client.id, field,
                old_value=old_value, new_value=value, request=request,
            )
        setattr(client, field, value)

    db.commit()
    db.refresh(client)
    return client
