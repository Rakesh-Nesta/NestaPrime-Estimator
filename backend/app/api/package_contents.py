import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.package_content import PackageContent
from app.models.project import Package
from app.models.sport import Sport

router = APIRouter(prefix="/package-contents", tags=["package-contents"])

# Q.1: "Packages | Budget/Standard/Premium contents | Per sport |
# Director [edits] | Sales customises items on the estimate." Read is
# open to whoever builds an Estimate (Sales/PM/Director) -- same shape
# as RegionalMultiplier's own read-only preview endpoint; only the
# Director may set the master content itself.
READ_ROLES = ("sales", "pm", "director")
WRITE_ROLES = ("director",)


class PackageContentOut(BaseModel):
    id: uuid.UUID
    sport_id: uuid.UUID
    tier: Package
    flooring_description: str
    structure_description: str
    lighting_description: str
    scope_description: str
    warranty_years: int | None
    updated_by_id: uuid.UUID
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[PackageContentOut])
def list_package_contents(
    sport_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """Optionally scoped to one sport (the Estimate builder only ever
    needs one sport's three tiers at a time)."""
    query = db.query(PackageContent)
    if sport_id is not None:
        query = query.filter(PackageContent.sport_id == sport_id)
    return query.order_by(PackageContent.sport_id, PackageContent.tier).all()


class PackageContentUpsert(BaseModel):
    flooring_description: str = Field(min_length=1)
    structure_description: str = Field(min_length=1)
    lighting_description: str = Field(min_length=1)
    scope_description: str = Field(min_length=1)
    warranty_years: int | None = Field(default=None, ge=0)


@router.put("/{sport_id}/{tier}", response_model=PackageContentOut)
def upsert_package_content(
    sport_id: uuid.UUID,
    tier: Package,
    payload: PackageContentUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Q.2 rule 6 precedent (Director-only master content): one row per
    (sport_id, tier) -- creates it the first time, replaces its content
    on every later call, same upsert shape as PUT
    /sport-margin-policies/{sport_id}."""
    if not db.query(Sport).filter(Sport.id == sport_id).first():
        raise HTTPException(status_code=404, detail="Sport not found")

    content = (
        db.query(PackageContent)
        .filter(PackageContent.sport_id == sport_id, PackageContent.tier == tier)
        .first()
    )
    if content is None:
        content = PackageContent(sport_id=sport_id, tier=tier, updated_by_id=current_user.id)
        db.add(content)

    content.flooring_description = payload.flooring_description
    content.structure_description = payload.structure_description
    content.lighting_description = payload.lighting_description
    content.scope_description = payload.scope_description
    content.warranty_years = payload.warranty_years
    content.updated_by_id = current_user.id

    db.commit()
    db.refresh(content)
    return content
