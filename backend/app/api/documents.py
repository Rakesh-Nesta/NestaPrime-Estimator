import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.pricing import GST_RATE_PERCENT, _target_margin_percent, compute_pricing
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.document import (
    CostSheet,
    CostSheetStatus,
    Estimate,
    EstimateOption,
    EstimateOptionClientStatus,
    EstimateStatus,
    Quotation,
    QuotationLine,
    QuotationStatus,
)
from app.models.margin_policy import MarginPolicy
from app.models.project import Package, Project
from app.models.sport import ProjectSport

cost_sheets_router = APIRouter(tags=["cost-sheets"])
estimates_router = APIRouter(tags=["estimates"])
quotations_router = APIRouter(tags=["quotations"])

# K.3: cost, contingency, markup and margin are never visible to Sales.
COST_ROLES = ("pm", "director")
# M.4: Sales may create/send Estimates & Quotations and record client
# status / won-lost, but the responses below strip cost-side fields for it.
DOCUMENT_ROLES = ("sales", "pm", "director")

ESTIMATE_VALIDITY_DAYS = 15
QUOTATION_VALIDITY_DAYS = 30
PRICE_RANGE_PERCENT = 5.0  # M.1: "range_pct [confirm 5%]"


def _document_no(project_no: str, prefix: str, revision_major: int, revision_minor: int = 0) -> str:
    """M.2 rule 10: the CS-/EST-/NPQ- documents reuse the project's own
    YYMM-#### suffix, e.g. project P-2609-0018 -> CS-2609-0018-R1."""
    suffix = project_no.split("-", 1)[1]
    rev = f"R{revision_major}" if revision_minor == 0 else f"R{revision_major}.{revision_minor}"
    return f"{prefix}-{suffix}-{rev}"


def _get_margin_policy(db: Session, client_type) -> MarginPolicy:
    policy = db.query(MarginPolicy).filter(MarginPolicy.client_type == client_type).first()
    if not policy:
        raise HTTPException(status_code=404, detail="No margin policy for this client type")
    return policy


# --------------------------------------------------------------------------
# Cost Sheets (M.1 stage 1)
# --------------------------------------------------------------------------


class CostSheetCreate(BaseModel):
    cost_total: float = Field(gt=0)


class CostSheetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    document_no: str
    revision_major: int
    revision_minor: int
    status: CostSheetStatus
    cost_total: float
    verified_by_id: uuid.UUID | None
    verified_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@cost_sheets_router.post(
    "/projects/{project_id}/cost-sheets", response_model=CostSheetOut, status_code=201
)
def create_cost_sheet(
    project_id: uuid.UUID,
    payload: CostSheetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = (
        db.query(CostSheet)
        .filter(CostSheet.project_id == project_id, CostSheet.status != CostSheetStatus.SUPERSEDED)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An active cost sheet already exists for this project; use /revise on it instead",
        )

    cost_sheet = CostSheet(
        project_id=project_id,
        document_no=_document_no(project.project_no, "CS", 1),
        cost_total=payload.cost_total,
        created_by_id=current_user.id,
    )
    db.add(cost_sheet)
    db.commit()
    db.refresh(cost_sheet)
    return cost_sheet


@cost_sheets_router.get("/projects/{project_id}/cost-sheets", response_model=list[CostSheetOut])
def list_cost_sheets(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    return (
        db.query(CostSheet)
        .filter(CostSheet.project_id == project_id)
        .order_by(CostSheet.revision_major.desc())
        .all()
    )


@cost_sheets_router.get("/cost-sheets/{cost_sheet_id}", response_model=CostSheetOut)
def get_cost_sheet(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    return cost_sheet


@cost_sheets_router.post("/cost-sheets/{cost_sheet_id}/verify", response_model=CostSheetOut)
def verify_cost_sheet(
    cost_sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.1: 'Draft -> Verified' by PM or Director."""
    cost_sheet = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not cost_sheet:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if cost_sheet.status != CostSheetStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot verify a cost sheet in {cost_sheet.status.value} status")

    cost_sheet.status = CostSheetStatus.VERIFIED
    cost_sheet.verified_by_id = current_user.id
    cost_sheet.verified_at = datetime.now(UTC)
    db.commit()
    db.refresh(cost_sheet)
    return cost_sheet


@cost_sheets_router.post(
    "/cost-sheets/{cost_sheet_id}/revise", response_model=CostSheetOut, status_code=201
)
def revise_cost_sheet(
    cost_sheet_id: uuid.UUID,
    payload: CostSheetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.2 rule 4: 'Any edit to a Verified Cost Sheet creates CS-R(n+1) in
    Draft requiring re-verification'; the prior revision becomes Superseded."""
    current = db.query(CostSheet).filter(CostSheet.id == cost_sheet_id).first()
    if not current:
        raise HTTPException(status_code=404, detail="Cost sheet not found")
    if current.status != CostSheetStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Only a Verified cost sheet can be revised")

    project = db.query(Project).filter(Project.id == current.project_id).first()
    new_revision = CostSheet(
        project_id=current.project_id,
        document_no=_document_no(project.project_no, "CS", current.revision_major + 1),
        revision_major=current.revision_major + 1,
        cost_total=payload.cost_total,
        created_by_id=current_user.id,
    )
    current.status = CostSheetStatus.SUPERSEDED
    db.add(new_revision)
    db.commit()
    db.refresh(new_revision)
    return new_revision


# --------------------------------------------------------------------------
# Estimates (M.1 stage 2)
# --------------------------------------------------------------------------


class EstimateOptionCreate(BaseModel):
    project_sport_id: uuid.UUID
    package: Package
    cost_for_option: float = Field(gt=0)


class EstimateCreate(BaseModel):
    options: list[EstimateOptionCreate] = Field(min_length=1)


class EstimateOptionOut(BaseModel):
    id: uuid.UUID
    estimate_id: uuid.UUID
    project_sport_id: uuid.UUID
    package: Package
    cost_for_option: float | None  # stripped to None for Sales (K.3)
    price_low: float
    price_high: float
    client_status: EstimateOptionClientStatus
    client_demand_note: str | None

    model_config = ConfigDict(from_attributes=True)


class EstimateOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    cost_sheet_id: uuid.UUID
    document_no: str
    revision_major: int
    revision_minor: int
    status: EstimateStatus
    client_status: str  # derived, M.4a #7
    sent_at: datetime | None
    expires_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime
    options: list[EstimateOptionOut]

    model_config = ConfigDict(from_attributes=True)


def _derived_client_status(options: list[EstimateOption]) -> str:
    """M.4a #7: 'approved if any option approved; rejected only if all
    rejected'."""
    statuses = {o.client_status for o in options}
    if EstimateOptionClientStatus.APPROVED in statuses:
        return "approved"
    if statuses == {EstimateOptionClientStatus.REJECTED}:
        return "rejected"
    if EstimateOptionClientStatus.DEMAND_RECEIVED in statuses:
        return "demand_received"
    return "pending"


def _estimate_to_out(estimate: Estimate, options: list[EstimateOption], role: str) -> EstimateOut:
    option_outs = []
    for o in options:
        out = EstimateOptionOut.model_validate(o)
        if role == "sales":
            out.cost_for_option = None
        option_outs.append(out)
    return EstimateOut(
        id=estimate.id,
        project_id=estimate.project_id,
        cost_sheet_id=estimate.cost_sheet_id,
        document_no=estimate.document_no,
        revision_major=estimate.revision_major,
        revision_minor=estimate.revision_minor,
        status=estimate.status,
        client_status=_derived_client_status(options),
        sent_at=estimate.sent_at,
        expires_at=estimate.expires_at,
        created_by_id=estimate.created_by_id,
        created_at=estimate.created_at,
        options=option_outs,
    )


@estimates_router.post(
    "/projects/{project_id}/estimates", response_model=EstimateOut, status_code=201
)
def create_estimate(
    project_id: uuid.UUID,
    payload: EstimateCreate,
    db: Session = Depends(get_db),
    # Estimate creation needs a per-option cost figure (K.3-protected), so
    # this endpoint -- unlike M.4's "Sales/PM/Director may create" -- is
    # PM/Director only until a real per-sport cost breakdown exists that
    # would let Sales create one without ever seeing the number.
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.2 rule 1: 'An Estimate cannot be created until its Cost Sheet is
    Verified.'"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cost_sheet = (
        db.query(CostSheet)
        .filter(CostSheet.project_id == project_id, CostSheet.status == CostSheetStatus.VERIFIED)
        .order_by(CostSheet.revision_major.desc())
        .first()
    )
    if not cost_sheet:
        raise HTTPException(status_code=400, detail="Project has no Verified cost sheet")

    client = db.query(Client).filter(Client.id == project.client_id).first()
    policy = _get_margin_policy(db, client.type)
    target = _target_margin_percent(policy)

    estimate = Estimate(
        project_id=project_id,
        cost_sheet_id=cost_sheet.id,
        document_no=_document_no(project.project_no, "EST", 1),
        created_by_id=current_user.id,
    )
    db.add(estimate)
    db.flush()

    options = []
    for option_payload in payload.options:
        project_sport = (
            db.query(ProjectSport)
            .filter(ProjectSport.id == option_payload.project_sport_id, ProjectSport.project_id == project_id)
            .first()
        )
        if not project_sport:
            raise HTTPException(
                status_code=404, detail=f"Sport selection {option_payload.project_sport_id} not on this project"
            )

        selling_ex_gst = option_payload.cost_for_option / (1 - target / 100)
        selling_incl_gst = selling_ex_gst * (1 + GST_RATE_PERCENT / 100)
        option = EstimateOption(
            estimate_id=estimate.id,
            project_sport_id=option_payload.project_sport_id,
            package=option_payload.package,
            cost_for_option=option_payload.cost_for_option,
            price_low=selling_incl_gst * (1 - PRICE_RANGE_PERCENT / 100),
            price_high=selling_incl_gst * (1 + PRICE_RANGE_PERCENT / 100),
        )
        db.add(option)
        options.append(option)

    db.commit()
    for o in options:
        db.refresh(o)
    return _estimate_to_out(estimate, options, current_user.role.value)


@estimates_router.get("/projects/{project_id}/estimates", response_model=list[EstimateOut])
def list_estimates(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    estimates = db.query(Estimate).filter(Estimate.project_id == project_id).all()
    out = []
    for e in estimates:
        options = db.query(EstimateOption).filter(EstimateOption.estimate_id == e.id).all()
        out.append(_estimate_to_out(e, options, current_user.role.value))
    return out


@estimates_router.get("/estimates/{estimate_id}", response_model=EstimateOut)
def get_estimate(
    estimate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate.id).all()
    return _estimate_to_out(estimate, options, current_user.role.value)


@estimates_router.post("/estimates/{estimate_id}/send", response_model=EstimateOut)
def send_estimate(
    estimate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.1: first send -> Sent, starts the 15-day validity (M.7.2 rule 3)."""
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if estimate.status != EstimateStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot send an estimate in {estimate.status.value} status")

    estimate.status = EstimateStatus.SENT
    estimate.sent_at = datetime.now(UTC)
    estimate.expires_at = estimate.sent_at + timedelta(days=ESTIMATE_VALIDITY_DAYS)
    db.commit()
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate.id).all()
    db.refresh(estimate)
    return _estimate_to_out(estimate, options, current_user.role.value)


class EstimateOptionStatusUpdate(BaseModel):
    client_status: EstimateOptionClientStatus
    client_demand_note: str | None = None


@estimates_router.patch(
    "/estimates/{estimate_id}/options/{option_id}/client-status", response_model=EstimateOptionOut
)
def update_option_client_status(
    estimate_id: uuid.UUID,
    option_id: uuid.UUID,
    payload: EstimateOptionStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.4: 'record Client approved / demand / rejected' -- Sales included."""
    option = (
        db.query(EstimateOption)
        .filter(EstimateOption.id == option_id, EstimateOption.estimate_id == estimate_id)
        .first()
    )
    if not option:
        raise HTTPException(status_code=404, detail="Estimate option not found")

    option.client_status = payload.client_status
    option.client_demand_note = payload.client_demand_note
    db.commit()
    db.refresh(option)
    out = EstimateOptionOut.model_validate(option)
    if current_user.role.value == "sales":
        out.cost_for_option = None
    return out


# --------------------------------------------------------------------------
# Quotations (M.1 stage 3)
# --------------------------------------------------------------------------


class QuotationCreate(BaseModel):
    estimate_id: uuid.UUID
    included_option_ids: list[uuid.UUID] = Field(min_length=1)
    discount_type: str | None = None
    discount_value: float = Field(default=0.0, ge=0)


class QuotationOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    estimate_id: uuid.UUID
    document_no: str
    revision_major: int
    revision_minor: int
    status: QuotationStatus
    cost_total: float | None  # stripped for Sales (K.3)
    target_margin_percent: float | None
    floor_margin_percent: float | None
    selling_price_ex_gst: float
    discount_type: str | None
    discount_value: float
    discount_amount: float
    selling_after_discount: float
    margin_percent: float | None  # stripped for Sales
    below_floor: bool | None  # stripped for Sales
    gst_amount: float
    quotation_total: float
    cost_basis_unverified: bool
    released_by_id: uuid.UUID | None
    released_at: datetime | None
    sent_at: datetime | None
    expires_at: datetime | None
    won_lost_reason: str | None
    created_by_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _quotation_to_out(quotation: Quotation, role: str) -> QuotationOut:
    out = QuotationOut.model_validate(quotation)
    if role == "sales":
        out.cost_total = None
        out.target_margin_percent = None
        out.floor_margin_percent = None
        out.margin_percent = None
        out.below_floor = None
    return out


@quotations_router.post(
    "/projects/{project_id}/quotations", response_model=QuotationOut, status_code=201
)
def create_quotation(
    project_id: uuid.UUID,
    payload: QuotationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.2 rule 2: needs at least one option Client approved or Client
    demand received. M.2 rule 11: covers the approved subset of sports."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    estimate = (
        db.query(Estimate).filter(Estimate.id == payload.estimate_id, Estimate.project_id == project_id).first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found on this project")

    included_options = []
    for option_id in payload.included_option_ids:
        option = (
            db.query(EstimateOption)
            .filter(EstimateOption.id == option_id, EstimateOption.estimate_id == estimate.id)
            .first()
        )
        if not option:
            raise HTTPException(status_code=404, detail=f"Estimate option {option_id} not found on this estimate")
        if option.client_status not in (
            EstimateOptionClientStatus.APPROVED,
            EstimateOptionClientStatus.DEMAND_RECEIVED,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Option {option_id} is not Client approved or Client demand received",
            )
        included_options.append(option)

    cost_sheet = db.query(CostSheet).filter(CostSheet.id == estimate.cost_sheet_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()
    policy = _get_margin_policy(db, client.type)

    cost_total = sum(float(o.cost_for_option) for o in included_options)
    pricing = compute_pricing(cost_total, policy, payload.discount_type, payload.discount_value)

    quotation = Quotation(
        project_id=project_id,
        estimate_id=estimate.id,
        document_no=_document_no(project.project_no, "NPQ", 1),
        cost_total=cost_total,
        target_margin_percent=pricing.target_margin_percent,
        floor_margin_percent=pricing.floor_margin_percent,
        selling_price_ex_gst=pricing.selling_price_ex_gst,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        discount_amount=pricing.discount_amount,
        selling_after_discount=pricing.selling_after_discount,
        margin_percent=pricing.margin_percent,
        below_floor=pricing.below_floor,
        gst_amount=pricing.gst_amount,
        quotation_total=pricing.quotation_total,
        cost_basis_unverified=(cost_sheet.status != CostSheetStatus.VERIFIED),
        created_by_id=current_user.id,
    )
    db.add(quotation)
    db.flush()
    for option in included_options:
        db.add(QuotationLine(quotation_id=quotation.id, estimate_option_id=option.id))
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.get("/projects/{project_id}/quotations", response_model=list[QuotationOut])
def list_quotations(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotations = db.query(Quotation).filter(Quotation.project_id == project_id).all()
    return [_quotation_to_out(q, current_user.role.value) for q in quotations]


@quotations_router.get("/quotations/{quotation_id}", response_model=QuotationOut)
def get_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.post("/quotations/{quotation_id}/release", response_model=QuotationOut)
def release_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """M.1: 'PM or Director release; Director if discount below floor or
    if the underlying Cost Sheet is Unverified.'"""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot release a quotation in {quotation.status.value} status")

    needs_director = quotation.below_floor or quotation.cost_basis_unverified
    if needs_director and current_user.role.value != "director":
        raise HTTPException(
            status_code=403,
            detail="Below-floor discount or unverified cost basis requires Director release",
        )

    quotation.status = QuotationStatus.RELEASED
    quotation.released_by_id = current_user.id
    quotation.released_at = datetime.now(UTC)
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.post("/quotations/{quotation_id}/send", response_model=QuotationOut)
def send_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.1: 'Released -> Sent', starts the 30-day validity."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.RELEASED:
        raise HTTPException(status_code=400, detail="Only a Released quotation can be sent")

    quotation.status = QuotationStatus.SENT
    quotation.sent_at = datetime.now(UTC)
    quotation.expires_at = quotation.sent_at + timedelta(days=QUOTATION_VALIDITY_DAYS)
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


class WonLostRequest(BaseModel):
    reason: str | None = None


@quotations_router.post("/quotations/{quotation_id}/mark-won", response_model=QuotationOut)
def mark_quotation_won(
    quotation_id: uuid.UUID,
    payload: WonLostRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    """M.2 rule 3: 'cannot be marked Won until the Cost Sheet is verified.'"""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != QuotationStatus.SENT:
        raise HTTPException(status_code=400, detail="Only a Sent quotation can be marked Won")
    if quotation.cost_basis_unverified:
        raise HTTPException(status_code=400, detail="Cannot mark Won while the cost basis is unverified")

    quotation.status = QuotationStatus.WON
    quotation.won_lost_reason = payload.reason
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)


@quotations_router.post("/quotations/{quotation_id}/mark-lost", response_model=QuotationOut)
def mark_quotation_lost(
    quotation_id: uuid.UUID,
    payload: WonLostRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*DOCUMENT_ROLES)),
):
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status not in (QuotationStatus.RELEASED, QuotationStatus.SENT):
        raise HTTPException(status_code=400, detail="Only a Released or Sent quotation can be marked Lost")

    quotation.status = QuotationStatus.LOST
    quotation.won_lost_reason = payload.reason
    db.commit()
    db.refresh(quotation)
    return _quotation_to_out(quotation, current_user.role.value)
