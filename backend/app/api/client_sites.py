import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.clients import READ_ROLES
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.client_site import ClientSite

router = APIRouter(prefix="/clients/{client_id}/sites", tags=["client-sites"])

WRITE_ROLES = ("sales", "pm", "director")


class ClientSiteCreate(BaseModel):
    label: str
    city: str
    site_address: str | None = None
    site_state_code: str | None = Field(default=None, max_length=10)
    notes: str | None = None


class ClientSiteUpdate(BaseModel):
    label: str | None = None
    city: str | None = None
    site_address: str | None = None
    site_state_code: str | None = Field(default=None, max_length=10)
    notes: str | None = None
    is_active: bool | None = None


class ClientSiteOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    label: str
    city: str
    site_address: str | None
    site_state_code: str | None
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _get_client_or_404(db: Session, client_id: uuid.UUID) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def get_site_or_404(db: Session, client_id: uuid.UUID, site_id: uuid.UUID) -> ClientSite:
    """P2 (Client 360 contract), nested-record validation -- same rule as client_contacts.py's
    own version: a Site fetched here must belong to the client_id in THIS URL, independent of
    Amendment 60 scoping. Exported (not underscore-prefixed): projects.py's site-attach flow
    reuses this exact check rather than re-implementing it."""
    site = db.query(ClientSite).filter(ClientSite.id == site_id).first()
    if site is None or site.client_id != client_id:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("", response_model=ClientSiteOut, status_code=201)
def create_site(
    client_id: uuid.UUID,
    payload: ClientSiteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    _get_client_or_404(db, client_id)
    label = payload.label.strip()
    city = payload.city.strip()
    if not label:
        raise HTTPException(status_code=400, detail="label cannot be blank")
    if not city:
        raise HTTPException(status_code=400, detail="city cannot be blank")
    site = ClientSite(
        client_id=client_id, label=label, city=city,
        site_address=payload.site_address, site_state_code=payload.site_state_code, notes=payload.notes,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("", response_model=list[ClientSiteOut])
def list_sites(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    _get_client_or_404(db, client_id)
    return (
        db.query(ClientSite)
        .filter(ClientSite.client_id == client_id)
        .order_by(ClientSite.created_at.desc())
        .all()
    )


@router.patch("/{site_id}", response_model=ClientSiteOut)
def update_site(
    client_id: uuid.UUID,
    site_id: uuid.UUID,
    payload: ClientSiteUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    site = get_site_or_404(db, client_id, site_id)
    sent = payload.model_fields_set
    if "label" in sent:
        label = (payload.label or "").strip()
        if not label:
            raise HTTPException(status_code=400, detail="label cannot be blank")
        site.label = label
    if "city" in sent:
        city = (payload.city or "").strip()
        if not city:
            raise HTTPException(status_code=400, detail="city cannot be blank")
        site.city = city
    for field in ("site_address", "site_state_code", "notes"):
        if field in sent:
            setattr(site, field, getattr(payload, field))
    if "is_active" in sent and payload.is_active is not None:
        site.is_active = payload.is_active
    db.commit()
    db.refresh(site)
    return site
