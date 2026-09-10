import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value, get_gst_rate_percent
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import ClientType
from app.models.document import GstMode
from app.models.margin_policy import MarginPolicy, SportMarginPolicy

margin_policies_router = APIRouter(prefix="/margin-policies", tags=["margin-policies"])
sport_margin_policies_router = APIRouter(prefix="/sport-margin-policies", tags=["margin-policies"])
pricing_router = APIRouter(prefix="/pricing", tags=["pricing"])

# K.3: cost, contingency, markup and margin are never visible to Sales or
# Procurement — enforced here at the API, same as rate-items.
READ_ROLES = ("pm", "director")
# K.2's sport-type floor override is Director-set ("... when the Director
# has defined one"), matching the Master Settings Q.1 write permission.
WRITE_ROLES = ("director",)

# Fallbacks used only when Part Q's Master Settings has no row yet for the
# key (e.g. a fresh test DB) -- see get_gst_rate_percent /
# get_current_setting_value in app.api.settings for the live values.
GST_RATE_PERCENT_DEFAULT = 18.0
COMPETITIVE_SEGMENT_POINTS_DEFAULT = 3.0
NON_COMPETITIVE_SEGMENT_POINTS_DEFAULT = 5.0


def _competitive_gap_points(db: Session, policy: MarginPolicy) -> float:
    """K.2: the +3 (competitive) or +5 (non-competitive) point gap. This
    flag is client-type-scoped only (no sport-level equivalent exists in
    the blueprint), so a sport floor override still uses the CLIENT's own
    gap -- only the floor itself is replaced."""
    if policy.competitive_segment:
        gap_str = get_current_setting_value(db, "competitive_segment_gap_points")
        return float(gap_str) if gap_str is not None else COMPETITIVE_SEGMENT_POINTS_DEFAULT
    gap_str = get_current_setting_value(db, "non_competitive_segment_gap_points")
    return float(gap_str) if gap_str is not None else NON_COMPETITIVE_SEGMENT_POINTS_DEFAULT


def _target_margin_percent(db: Session, policy: MarginPolicy) -> float:
    """K.2: 'target = floor + (competitive_segment ? 3 : 5) points.'"""
    return float(policy.floor_margin_percent) + _competitive_gap_points(db, policy)


def get_sport_margin_policy(db: Session, sport_id) -> SportMarginPolicy | None:
    return db.query(SportMarginPolicy).filter(SportMarginPolicy.sport_id == sport_id).first()


def effective_floor_and_target(
    db: Session, client_policy: MarginPolicy, sport_id=None
) -> tuple[float, float]:
    """K.2: 'A sport-type floor ... replaces the client floor for that
    sport when the Director has defined one.' Falls back to the client
    floor when no sport override exists. Target is always re-derived from
    whichever floor applies, using the client's own competitive_segment
    gap (see _competitive_gap_points)."""
    floor = float(client_policy.floor_margin_percent)
    if sport_id is not None:
        sport_policy = get_sport_margin_policy(db, sport_id)
        if sport_policy:
            floor = float(sport_policy.floor_margin_percent)
    target = floor + _competitive_gap_points(db, client_policy)
    return floor, target


def cost_weighted_floor_and_target(
    db: Session, client_policy: MarginPolicy, cost_and_sport_ids: list[tuple[float, "uuid.UUID | None"]]
) -> tuple[float, float]:
    """K.2: 'Multi-sport project: floor = cost-weighted average of the
    applicable floors.' Each (cost, sport_id) pair contributes its own
    effective floor (sport override or client floor), weighted by its
    own cost share; target is then re-derived from that blended floor."""
    total_cost = sum(cost for cost, _ in cost_and_sport_ids)
    if total_cost <= 0:
        floor, target = effective_floor_and_target(db, client_policy, None)
        return floor, target
    weighted_floor = sum(
        cost * effective_floor_and_target(db, client_policy, sport_id)[0]
        for cost, sport_id in cost_and_sport_ids
    ) / total_cost
    target = weighted_floor + _competitive_gap_points(db, client_policy)
    return weighted_floor, target


class MarginPolicyOut(BaseModel):
    id: uuid.UUID
    client_type: ClientType
    floor_margin_percent: float
    competitive_segment: bool
    target_margin_percent: float = 0.0  # derived; _to_out() sets the real value

    model_config = ConfigDict(from_attributes=True)


def _policy_to_out(db: Session, policy: MarginPolicy) -> MarginPolicyOut:
    out = MarginPolicyOut.model_validate(policy)
    out.target_margin_percent = _target_margin_percent(db, policy)
    return out


@margin_policies_router.get("", response_model=list[MarginPolicyOut])
def list_margin_policies(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    policies = db.query(MarginPolicy).order_by(MarginPolicy.client_type).all()
    return [_policy_to_out(db, p) for p in policies]


class SportMarginPolicyOut(BaseModel):
    id: uuid.UUID
    sport_id: uuid.UUID
    floor_margin_percent: float

    model_config = ConfigDict(from_attributes=True)


class SportMarginPolicyUpsert(BaseModel):
    floor_margin_percent: float = Field(ge=0, lt=100)


@sport_margin_policies_router.get("", response_model=list[SportMarginPolicyOut])
def list_sport_margin_policies(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return db.query(SportMarginPolicy).all()


@sport_margin_policies_router.put("/{sport_id}", response_model=SportMarginPolicyOut, status_code=200)
def upsert_sport_margin_policy(
    sport_id: uuid.UUID,
    payload: SportMarginPolicyUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """K.2: Director-defined sport-type floor override -- 'replaces the
    client floor for that sport when the Director has defined one.'"""
    from app.models.sport import Sport

    sport = db.query(Sport).filter(Sport.id == sport_id).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")

    policy = get_sport_margin_policy(db, sport_id)
    if policy:
        policy.floor_margin_percent = payload.floor_margin_percent
    else:
        policy = SportMarginPolicy(sport_id=sport_id, floor_margin_percent=payload.floor_margin_percent)
        db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@sport_margin_policies_router.delete("/{sport_id}", status_code=204)
def delete_sport_margin_policy(
    sport_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Removes the override -- the sport reverts to its client-type floor."""
    policy = get_sport_margin_policy(db, sport_id)
    if not policy:
        raise HTTPException(status_code=404, detail="No margin override for this sport")
    db.delete(policy)
    db.commit()


class PricingResult(BaseModel):
    cost: float
    floor_margin_percent: float
    target_margin_percent: float
    selling_price_ex_gst: float
    discount_amount: float
    selling_after_discount: float
    margin_percent: float
    markup_percent: float
    below_floor: bool
    gst_rate_percent: float
    gst_amount: float
    quotation_total: float
    gst_mode: GstMode


def compute_pricing(
    db: Session,
    cost: float,
    floor: float,
    target: float,
    discount_type: str | None,
    discount_value: float,
    gst_mode: GstMode = GstMode.EXCLUSIVE,
) -> PricingResult:
    """K.1 steps 7-12 + K.2/K.4, shared by /pricing/quote and the document
    state machine (Estimate options, Quotations) so both price identically.
    Callers resolve floor/target beforehand -- via effective_floor_and_target
    (single sport) or cost_weighted_floor_and_target (multi-sport) -- since
    K.2's sport-type override means the applicable floor is not always the
    client-type policy's own floor.

    gst_mode (Part L 'Price basis' toggle, Tender Mode only -- see
    GstMode's own docstring) changes only where GST and the discount fall
    relative to each other, never how target margin is defined: target
    margin is always anchored to the ex-GST base in both modes, so
    margin_percent stays comparable regardless of which basis a tender
    happens to quote in.
    - EXCLUSIVE (default, every private/non-Tender quotation): the
      target-margin price is already the ex-GST base; discount is taken
      off it; GST is added on top to reach quotation_total.
    - INCLUSIVE: the target-margin price is grossed up by GST first (the
      figure actually comparable to a competitor's inclusive tender bid);
      discount is taken off that grossed-up figure to land directly on
      quotation_total; the ex-GST base (and so margin) is then backed out
      of that final total."""
    if target >= 100:
        raise HTTPException(status_code=400, detail="Target margin must be below 100%")

    target_price_ex_gst = cost / (1 - target / 100)
    gst_rate_percent = get_gst_rate_percent(db)

    if gst_mode == GstMode.INCLUSIVE:
        target_price = target_price_ex_gst * (1 + gst_rate_percent / 100)
    else:
        target_price = target_price_ex_gst

    if discount_type == "percent":
        discount_amount = target_price * discount_value / 100
    elif discount_type == "amount":
        discount_amount = discount_value
    else:
        discount_amount = 0.0

    price_after_discount = target_price - discount_amount
    if price_after_discount <= 0:
        raise HTTPException(status_code=400, detail="Discount cannot reduce selling price to zero or below")

    if gst_mode == GstMode.INCLUSIVE:
        quotation_total = price_after_discount
        selling_after_discount = quotation_total / (1 + gst_rate_percent / 100)
        gst_amount = quotation_total - selling_after_discount
    else:
        selling_after_discount = price_after_discount
        gst_amount = selling_after_discount * gst_rate_percent / 100
        quotation_total = selling_after_discount + gst_amount

    margin_percent = (selling_after_discount - cost) / selling_after_discount * 100
    markup_percent = (selling_after_discount - cost) / cost * 100
    below_floor = margin_percent < floor

    return PricingResult(
        cost=cost,
        floor_margin_percent=floor,
        target_margin_percent=target,
        selling_price_ex_gst=target_price_ex_gst,
        discount_amount=discount_amount,
        selling_after_discount=selling_after_discount,
        margin_percent=margin_percent,
        markup_percent=markup_percent,
        below_floor=below_floor,
        gst_rate_percent=gst_rate_percent,
        gst_amount=gst_amount,
        quotation_total=quotation_total,
        gst_mode=gst_mode,
    )


class PricingQuoteRequest(BaseModel):
    cost_incl_contingency: float = Field(gt=0)
    client_type: ClientType
    sport_id: uuid.UUID | None = None  # K.2 sport-type floor override, if the Director has set one
    discount_type: str | None = None  # "percent" | "amount" | None
    discount_value: float = Field(default=0.0, ge=0)
    # Part L "Price basis" toggle -- a standalone sandbox calculator, not
    # tied to a real Quotation, so unlike the document endpoints this
    # isn't gated to Tender Mode; anyone sanity-checking "what would an
    # inclusive tender bid look like" can flip it.
    gst_mode: GstMode = GstMode.EXCLUSIVE


class PricingQuoteOut(BaseModel):
    cost_incl_contingency: float
    floor_margin_percent: float
    target_margin_percent: float
    selling_price_ex_gst: float  # K.1 steps 7-8, before discount
    discount_amount: float
    selling_after_discount: float  # K.1 step 9
    margin_percent: float  # K.1 step 10 / K.2
    markup_percent: float  # K.2
    below_floor: bool  # K.1 step 10: below floor -> Director approval
    gst_rate_percent: float
    gst_amount: float  # K.1 step 11
    quotation_total: float  # K.1 step 12
    gst_mode: GstMode


@pricing_router.post("/quote", response_model=PricingQuoteOut)
def price_quote(
    payload: PricingQuoteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """K.1 steps 7-12 + K.2/K.4. Takes an already-computed cost incl.
    contingency (the real cost/take-off engine is not built yet -- D.3,
    E.2 and F.5's quantity math are still pending real per-project area
    aggregation) and prices it exactly as the blueprint specifies."""
    policy = db.query(MarginPolicy).filter(MarginPolicy.client_type == payload.client_type).first()
    if not policy:
        raise HTTPException(status_code=404, detail="No margin policy for this client type")

    floor, target = effective_floor_and_target(db, policy, payload.sport_id)
    result = compute_pricing(
        db, payload.cost_incl_contingency, floor, target, payload.discount_type, payload.discount_value,
        gst_mode=payload.gst_mode,
    )
    return PricingQuoteOut(
        cost_incl_contingency=result.cost,
        floor_margin_percent=result.floor_margin_percent,
        target_margin_percent=result.target_margin_percent,
        selling_price_ex_gst=result.selling_price_ex_gst,
        discount_amount=result.discount_amount,
        selling_after_discount=result.selling_after_discount,
        margin_percent=result.margin_percent,
        markup_percent=result.markup_percent,
        below_floor=result.below_floor,
        gst_rate_percent=result.gst_rate_percent,
        gst_amount=result.gst_amount,
        quotation_total=result.quotation_total,
        gst_mode=result.gst_mode,
    )
