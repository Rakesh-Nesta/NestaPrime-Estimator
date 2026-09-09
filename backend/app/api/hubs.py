import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.hub import Hub

router = APIRouter(prefix="/hubs", tags=["hubs"])

# Same shape as ScopeItem/Sport: whoever creates a project needs to see
# the hub list to pick from (B.1 field #4); only the Director maintains
# the master list itself (Q.2 rule 6 precedent).
READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("director",)


class HubOut(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    state_code: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[HubOut])
def list_hubs(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(Hub)
    if not include_inactive:
        query = query.filter(Hub.is_active.is_(True))
    return query.order_by(Hub.name).all()


class HubCreate(BaseModel):
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state_code: str = Field(min_length=1)


class HubUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    state_code: str | None = None
    is_active: bool | None = None


@router.post("", response_model=HubOut, status_code=201)
def create_hub(
    payload: HubCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    if db.query(Hub).filter(Hub.name == payload.name).first():
        raise HTTPException(status_code=409, detail=f"A hub named '{payload.name}' already exists")
    hub = Hub(**payload.model_dump())
    db.add(hub)
    db.commit()
    db.refresh(hub)
    return hub


@router.patch("/{hub_id}", response_model=HubOut)
def update_hub(
    hub_id: uuid.UUID,
    payload: HubUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    hub = db.query(Hub).filter(Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hub, field, value)
    db.commit()
    db.refresh(hub)
    return hub
