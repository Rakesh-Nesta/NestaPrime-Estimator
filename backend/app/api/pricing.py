import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value, get_gst_rate_percent
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import ClientType
from app.models.margin_policy import MarginPolicy

margin_policies_router = APIRouter(prefix="/margin-policies", tags=["margin-policies"])
pricing_router = APIRouter(prefix="/pricing", tags=["pricing"])

# K.3: cost, contingency, markup and margin are never visible to Sales or
# Procurement — enforced here at the API, same as rate-items.
READ_ROLES = ("pm", "director")

# Fallbacks used only when Part Q's Master Settings has no row yet for the
# key (e.g. a fresh test DB) -- see get_gst_rate_percent /
# get_current_setting_value in app.api.settings for the live values.
GST_RATE_PERCENT_DEFAULT = 18.0
COMPETITIVE_SEGMENT_POINTS_DEFAULT = 3.0
NON_COMPETITIVE_SEGMENT_POINTS_DEFAULT = 5.0


def _target_margin_percent(db: Session, policy: MarginPolicy) -> float:
    """K.2: 'target = floor + (competitive_segment ? 3 : 5) points.'"""
    if policy.competitive_segment:
        gap_str = get_current_setting_value(db, "competitive_segment_gap_points")
        gap = float(gap_str) if gap_str is not None else COMPETITIVE_SEGMENT_POINTS_DEFAULT
    else:
        gap_str = get_current_setting_value(db, "non_competitive_segment_gap_points")
        gap = float(gap_str) if gap_str is not None else NON_COMPETITIVE_SEGMENT_POINTS_DEFAULT
    return float(policy.floor_margin_percent) + gap


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


def compute_pricing(
    db: Session,
    cost: float,
    policy: MarginPolicy,
    discount_type: str | None,
    discount_value: float,
) -> PricingResult:
    """K.1 steps 7-12 + K.2/K.4, shared by /pricing/quote and the document
    state machine (Estimate options, Quotations) so both price identically."""
    floor = float(policy.floor_margin_percent)
    target = _target_margin_percent(db, policy)
    if target >= 100:
        raise HTTPException(status_code=400, detail="Target margin must be below 100%")

    selling_price_ex_gst = cost / (1 - target / 100)

    if discount_type == "percent":
        discount_amount = selling_price_ex_gst * discount_value / 100
    elif discount_type == "amount":
        discount_amount = discount_value
    else:
        discount_amount = 0.0

    selling_after_discount = selling_price_ex_gst - discount_amount
    if selling_after_discount <= 0:
        raise HTTPException(status_code=400, detail="Discount cannot reduce selling price to zero or below")

    margin_percent = (selling_after_discount - cost) / selling_after_discount * 100
    markup_percent = (selling_after_discount - cost) / cost * 100
    below_floor = margin_percent < floor

    gst_rate_percent = get_gst_rate_percent(db)
    gst_amount = selling_after_discount * gst_rate_percent / 100
    quotation_total = selling_after_discount + gst_amount

    return PricingResult(
        cost=cost,
        floor_margin_percent=floor,
        target_margin_percent=target,
        selling_price_ex_gst=selling_price_ex_gst,
        discount_amount=discount_amount,
        selling_after_discount=selling_after_discount,
        margin_percent=margin_percent,
        markup_percent=markup_percent,
        below_floor=below_floor,
        gst_rate_percent=gst_rate_percent,
        gst_amount=gst_amount,
        quotation_total=quotation_total,
    )


class PricingQuoteRequest(BaseModel):
    cost_incl_contingency: float = Field(gt=0)
    client_type: ClientType
    discount_type: str | None = None  # "percent" | "amount" | None
    discount_value: float = Field(default=0.0, ge=0)


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

    result = compute_pricing(
        db, payload.cost_incl_contingency, policy, payload.discount_type, payload.discount_value
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
    )
