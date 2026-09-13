import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.cross_sell_addon import AddonCategory, CrossSellAddon, CrossSellAddonSport
from app.models.document import EstimateOption, EstimateOptionAddon
from app.models.sport import ProjectSport, Sport

# Amendment 3 (Annexure 2): "Complete Your Facility" cross-sell.
# Catalog management is Director-only (Master Settings pattern, same as
# every other reference-data table in this app). Suggesting/adding at the
# Estimate step is open to whoever can work an Estimate at all (K.3: cost
# and margin still hidden from Sales, same split as everywhere else).
CATALOG_WRITE_ROLES = ("director",)
CATALOG_READ_ROLES = ("pm", "director")
ESTIMATE_ROLES = ("sales", "pm", "director")

cross_sell_addons_router = APIRouter(prefix="/cross-sell-addons", tags=["cross-sell"])
estimate_option_addons_router = APIRouter(tags=["cross-sell"])


def _selling_price(cost: float, margin_percent: float) -> float:
    """Same target-margin formula as K.2 everywhere else: selling = cost /
    (1 - margin%)."""
    return cost / (1 - margin_percent / 100)


class CrossSellAddonCreate(BaseModel):
    name: str
    category: AddonCategory
    description: str | None = None
    cost: float | None = None
    unit: str | None = None
    margin_percent: float | None = None
    all_sports: bool = False


class CrossSellAddonUpdate(BaseModel):
    name: str | None = None
    category: AddonCategory | None = None
    description: str | None = None
    cost: float | None = None
    unit: str | None = None
    margin_percent: float | None = None
    all_sports: bool | None = None
    is_active: bool | None = None


class CrossSellAddonOut(BaseModel):
    id: uuid.UUID
    name: str
    category: AddonCategory
    description: str | None
    cost: float | None
    unit: str | None
    margin_percent: float | None
    selling_price: float | None = None  # derived; set below when cost+margin present
    all_sports: bool
    is_active: bool
    sport_ids: list[uuid.UUID] = []

    model_config = ConfigDict(from_attributes=True)


def _addon_to_out(db: Session, addon: CrossSellAddon) -> CrossSellAddonOut:
    out = CrossSellAddonOut.model_validate(addon)
    if addon.cost is not None and addon.margin_percent is not None:
        out.selling_price = _selling_price(float(addon.cost), float(addon.margin_percent))
    out.sport_ids = [
        row.sport_id for row in db.query(CrossSellAddonSport).filter(CrossSellAddonSport.addon_id == addon.id).all()
    ]
    return out


def _validate_activation(payload_is_active: bool | None, cost: float | None, margin_percent: float | None) -> None:
    """"Inactive... until a PM/Director enters a real cost" (Section 7
    spec) -- an addon can't go active without both cost and margin set,
    so the Estimate-step suggestion list can never show an un-priced
    add-on by accident."""
    if payload_is_active and (cost is None or margin_percent is None):
        raise HTTPException(
            status_code=422, detail="Cannot activate an add-on with no cost and margin set"
        )


# ---------------------------------------------------------------------------
# Catalog CRUD (Director-only)
# ---------------------------------------------------------------------------


@cross_sell_addons_router.post("", response_model=CrossSellAddonOut, status_code=201)
def create_addon(
    payload: CrossSellAddonCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_WRITE_ROLES)),
):
    # New addons always start inactive -- see _validate_activation's own
    # docstring; this mirrors J.1's "Manual entry -> saved as Unverified"
    # discipline for the Rate Sheet.
    addon = CrossSellAddon(**payload.model_dump(), is_active=False)
    db.add(addon)
    db.commit()
    db.refresh(addon)
    return _addon_to_out(db, addon)


@cross_sell_addons_router.get("", response_model=list[CrossSellAddonOut])
def list_addons(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_READ_ROLES)),
):
    addons = db.query(CrossSellAddon).order_by(CrossSellAddon.category, CrossSellAddon.name).all()
    return [_addon_to_out(db, a) for a in addons]


@cross_sell_addons_router.patch("/{addon_id}", response_model=CrossSellAddonOut)
def update_addon(
    addon_id: uuid.UUID,
    payload: CrossSellAddonUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_WRITE_ROLES)),
):
    addon = db.query(CrossSellAddon).filter(CrossSellAddon.id == addon_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")

    updates = payload.model_dump(exclude_unset=True)
    effective_cost = updates.get("cost", addon.cost)
    effective_margin = updates.get("margin_percent", addon.margin_percent)
    effective_is_active = updates.get("is_active", addon.is_active)
    _validate_activation(effective_is_active, effective_cost, effective_margin)

    for field, value in updates.items():
        setattr(addon, field, value)
    db.commit()
    db.refresh(addon)
    return _addon_to_out(db, addon)


class AddonSportsUpdate(BaseModel):
    sport_ids: list[uuid.UUID]


@cross_sell_addons_router.put("/{addon_id}/sports", response_model=CrossSellAddonOut)
def set_addon_sports(
    addon_id: uuid.UUID,
    payload: AddonSportsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CATALOG_WRITE_ROLES)),
):
    """Replaces the full sport-tag set for this addon in one call --
    simpler for a checkbox-grid UI than incremental add/remove calls."""
    addon = db.query(CrossSellAddon).filter(CrossSellAddon.id == addon_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")

    known_sport_ids = {s.id for s in db.query(Sport.id).filter(Sport.id.in_(payload.sport_ids)).all()}
    missing = set(payload.sport_ids) - known_sport_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown sport id(s): {sorted(str(m) for m in missing)}")

    db.query(CrossSellAddonSport).filter(CrossSellAddonSport.addon_id == addon_id).delete()
    for sport_id in payload.sport_ids:
        db.add(CrossSellAddonSport(addon_id=addon_id, sport_id=sport_id))
    db.commit()
    db.refresh(addon)
    return _addon_to_out(db, addon)


# ---------------------------------------------------------------------------
# Suggestions at the Estimate step + one-tap add/remove
# ---------------------------------------------------------------------------

MAX_SUGGESTIONS = 5


class SuggestedAddonOut(BaseModel):
    id: uuid.UUID
    name: str
    category: AddonCategory
    description: str | None
    unit: str | None
    selling_price: float
    cost: float | None  # stripped to None for Sales (K.3)
    margin_percent: float | None  # stripped to None for Sales (K.3)

    model_config = ConfigDict(from_attributes=True)


@cross_sell_addons_router.get(
    "/suggestions/for-project/{project_id}", response_model=list[SuggestedAddonOut]
)
def suggest_addons_for_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ESTIMATE_ROLES)),
):
    """Up to 5 active add-ons matched to the project's own selected
    sports (or tagged all_sports, e.g. AMC) -- Amendment 3's "4-5
    sport-matched add-ons." Never forced: this only ever suggests, the
    caller decides whether to add any of them."""
    project_sport_ids = {
        row.sport_id
        for row in db.query(ProjectSport.sport_id).filter(ProjectSport.project_id == project_id).all()
    }

    query = db.query(CrossSellAddon).filter(CrossSellAddon.is_active.is_(True))
    all_sports_addons = query.filter(CrossSellAddon.all_sports.is_(True)).all()

    sport_matched_addons = []
    if project_sport_ids:
        matched_ids = {
            row.addon_id
            for row in db.query(CrossSellAddonSport)
            .filter(CrossSellAddonSport.sport_id.in_(project_sport_ids))
            .all()
        }
        if matched_ids:
            sport_matched_addons = (
                query.filter(CrossSellAddon.id.in_(matched_ids), CrossSellAddon.all_sports.is_(False)).all()
            )

    combined = {a.id: a for a in [*all_sports_addons, *sport_matched_addons]}
    addons = sorted(combined.values(), key=lambda a: (a.category.value, a.name))[:MAX_SUGGESTIONS]

    results = []
    for a in addons:
        out = SuggestedAddonOut(
            id=a.id, name=a.name, category=a.category, description=a.description, unit=a.unit,
            selling_price=_selling_price(float(a.cost), float(a.margin_percent)),
            cost=float(a.cost), margin_percent=float(a.margin_percent),
        )
        if current_user.role.value == "sales":
            out.cost = None
            out.margin_percent = None
        results.append(out)
    return results


class EstimateOptionAddonCreate(BaseModel):
    addon_id: uuid.UUID


class EstimateOptionAddonOut(BaseModel):
    id: uuid.UUID
    estimate_option_id: uuid.UUID
    addon_id: uuid.UUID
    name: str
    category: str
    unit: str | None
    selling_price: float
    cost: float | None  # stripped to None for Sales (K.3)
    margin_percent: float | None  # stripped to None for Sales (K.3)

    model_config = ConfigDict(from_attributes=True)


def _strip_addon_for_sales(out: EstimateOptionAddonOut, role: str) -> EstimateOptionAddonOut:
    if role == "sales":
        out.cost = None
        out.margin_percent = None
    return out


@estimate_option_addons_router.post(
    "/estimate-options/{option_id}/addons", response_model=EstimateOptionAddonOut, status_code=201
)
def add_addon_to_option(
    option_id: uuid.UUID,
    payload: EstimateOptionAddonCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ESTIMATE_ROLES)),
):
    option = db.query(EstimateOption).filter(EstimateOption.id == option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="Estimate option not found")

    addon = db.query(CrossSellAddon).filter(CrossSellAddon.id == payload.addon_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    if not addon.is_active or addon.cost is None or addon.margin_percent is None:
        raise HTTPException(status_code=400, detail="This add-on is not active/priced yet")

    row = EstimateOptionAddon(
        estimate_option_id=option_id,
        addon_id=addon.id,
        name=addon.name,
        category=addon.category.value,
        unit=addon.unit,
        selling_price=_selling_price(float(addon.cost), float(addon.margin_percent)),
        cost=float(addon.cost),
        margin_percent=float(addon.margin_percent),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _strip_addon_for_sales(EstimateOptionAddonOut.model_validate(row), current_user.role.value)


@estimate_option_addons_router.get(
    "/estimate-options/{option_id}/addons", response_model=list[EstimateOptionAddonOut]
)
def list_option_addons(
    option_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ESTIMATE_ROLES)),
):
    if not db.query(EstimateOption).filter(EstimateOption.id == option_id).first():
        raise HTTPException(status_code=404, detail="Estimate option not found")
    rows = (
        db.query(EstimateOptionAddon)
        .filter(EstimateOptionAddon.estimate_option_id == option_id)
        .order_by(EstimateOptionAddon.created_at)
        .all()
    )
    return [
        _strip_addon_for_sales(EstimateOptionAddonOut.model_validate(r), current_user.role.value) for r in rows
    ]


@estimate_option_addons_router.delete("/estimate-option-addons/{row_id}", status_code=204)
def remove_addon_from_option(
    row_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ESTIMATE_ROLES)),
):
    row = db.query(EstimateOptionAddon).filter(EstimateOptionAddon.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Estimate option add-on not found")
    db.delete(row)
    db.commit()
