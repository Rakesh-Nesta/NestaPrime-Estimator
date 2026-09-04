import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

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


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    type: ClientType
    contact_name: str | None
    phone: str | None
    email: str | None
    overdue_flag: bool
    blacklist_flag: bool

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
