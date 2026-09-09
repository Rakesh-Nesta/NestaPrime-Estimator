import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.api.settings import get_current_setting_value
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client, ClientType
from app.models.project import Package

router = APIRouter(prefix="/clients", tags=["clients"])

# B.2's automatic-triggers table gives exactly one worked example --
# "Client = School -> Package Standard . Payment 40/40/20" -- for package
# and payment-term defaults; every other client type has no figure
# anywhere in the document, same honesty as pdf_documents.py's own
# WARRANTY_YEARS_DEFAULT for that identical table row. Director-overridable
# via Settings keys default_package_<client_type> /
# default_payment_terms_<client_type>, the same override mechanism
# _warranty_years already uses.
PACKAGE_DEFAULT: dict[ClientType, Package] = {ClientType.SCHOOL: Package.STANDARD}
PAYMENT_TERMS_DEFAULT: dict[ClientType, str] = {ClientType.SCHOOL: "40/40/20"}


def _default_package(db: Session, client_type: ClientType) -> Package | None:
    value = get_current_setting_value(db, f"default_package_{client_type.value}")
    if value is not None:
        return Package(value)
    return PACKAGE_DEFAULT.get(client_type)


def _default_payment_terms(db: Session, client_type: ClientType) -> str | None:
    value = get_current_setting_value(db, f"default_payment_terms_{client_type.value}")
    if value is not None:
        return value
    return PAYMENT_TERMS_DEFAULT.get(client_type)


class ClientCreate(BaseModel):
    name: str
    type: ClientType
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    billing_address: str | None = None
    gstin: str | None = None
    pan: str | None = None
    # B.2: left blank, this fills from the client type's own payment-term
    # template (_default_payment_terms) at creation time -- a starting
    # value, not a locked one; Sales can type over it here before saving.
    payment_terms: str | None = None
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
    payment_terms: str | None
    overdue_flag: bool
    blacklist_flag: bool
    whatsapp_opt_in: bool
    email_opt_in: bool
    consent_date: date | None

    model_config = ConfigDict(from_attributes=True)


class ClientTypeDefaultsOut(BaseModel):
    package: Package | None
    payment_terms: str | None


# Client creation isn't itemised in M.4's matrix, but it's the natural
# extension of "create cost sheet / estimate / quotation" — Sales is where
# leads enter the system, so Sales/PM/Director all create clients.
@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    fields = payload.model_dump()
    if fields["payment_terms"] is None:
        fields["payment_terms"] = _default_payment_terms(db, payload.type)
    client = Client(**fields)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/type-defaults/{client_type}", response_model=ClientTypeDefaultsOut)
def get_client_type_defaults(
    client_type: ClientType,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    """B.2: 'Client = School -> Package Standard . Payment 40/40/20' --
    lets the New Project / New Client forms preview and prefill both
    values before the client (and its payment_terms) or the project (and
    its package) actually get created. Either value may come back None
    when this client type has no configured default -- the caller then
    falls back to asking for an explicit choice, same as the API itself
    does at creation time."""
    return ClientTypeDefaultsOut(
        package=_default_package(db, client_type),
        payment_terms=_default_payment_terms(db, client_type),
    )


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
