import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import ClientType
from app.models.margin_policy import MarginPolicy

margin_policies_router = APIRouter(prefix="/margin-policies", tags=["margin-policies"])
pricing_router = APIRouter(prefix="/pricing", tags=["pricing"])

# K.3: cost, contingency, markup and margin are never visible to Sales or
# Procurement — enforced here at the API, same as rate-items.
READ_ROLES = ("pm", "director")

# K.4: "The GST rate itself (18%) is a Master Setting (Q.1), not
# hard-coded, in case it ever changes" -- Part Q (Master Settings) isn't
# built yet, so this stays a documented constant until it is.
GST_RATE_PERCENT = 18.0

COMPETITIVE_SEGMENT_POINTS = 3.0
NON_COMPETITIVE_SEGMENT_POINTS = 5.0


def _target_margin_percent(policy: MarginPolicy) -> float:
    """K.2: 'target = floor + (competitive_segment ? 3 : 5) points.'"""
    gap = COMPETITIVE_SEGMENT_POINTS if policy.competitive_segment else NON_COMPETITIVE_SEGMENT_POINTS
    return float(policy.floor_margin_percent) + gap


class MarginPolicyOut(BaseModel):
    id: uuid.UUID
    client_type: ClientType
    floor_margin_percent: float
    competitive_segment: bool
    target_margin_percent: float = 0.0  # derived; _to_out() sets the real value

    model_config = ConfigDict(from_attributes=True)


def _policy_to_out(policy: MarginPolicy) -> MarginPolicyOut:
    out = MarginPolicyOut.model_validate(policy)
    out.target_margin_percent = _target_margin_percent(policy)
    return out


@margin_policies_router.get("", response_model=list[MarginPolicyOut])
def list_margin_policies(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    policies = db.query(MarginPolicy).order_by(MarginPolicy.client_type).all()
    return [_policy_to_out(p) for p in policies]


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

    floor = float(policy.floor_margin_percent)
    target = _target_margin_percent(policy)
    if target >= 100:
        raise HTTPException(status_code=400, detail="Target margin must be below 100%")

    cost = payload.cost_incl_contingency
    selling_price_ex_gst = cost / (1 - target / 100)

    if payload.discount_type == "percent":
        discount_amount = selling_price_ex_gst * payload.discount_value / 100
    elif payload.discount_type == "amount":
        discount_amount = payload.discount_value
    else:
        discount_amount = 0.0

    selling_after_discount = selling_price_ex_gst - discount_amount
    if selling_after_discount <= 0:
        raise HTTPException(status_code=400, detail="Discount cannot reduce selling price to zero or below")

    margin_percent = (selling_after_discount - cost) / selling_after_discount * 100
    markup_percent = (selling_after_discount - cost) / cost * 100
    below_floor = margin_percent < floor

    gst_amount = selling_after_discount * GST_RATE_PERCENT / 100
    quotation_total = selling_after_discount + gst_amount

    return PricingQuoteOut(
        cost_incl_contingency=cost,
        floor_margin_percent=floor,
        target_margin_percent=target,
        selling_price_ex_gst=selling_price_ex_gst,
        discount_amount=discount_amount,
        selling_after_discount=selling_after_discount,
        margin_percent=margin_percent,
        markup_percent=markup_percent,
        below_floor=below_floor,
        gst_rate_percent=GST_RATE_PERCENT,
        gst_amount=gst_amount,
        quotation_total=quotation_total,
    )
