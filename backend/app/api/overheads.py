import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet
from app.api.tender import compute_bg_cost
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheetLine, WorkPackage
from app.models.project import Project
from app.models.rate_item import RateSource

overheads_router = APIRouter(tags=["overheads"])

COST_ROLES = ("pm", "director")


# ---------------------------------------------------------------------------
# K.1 step 3: "+ Site establishment % of (1+2) + freight + crane hire."
# The blueprint gives the freight formula (Part B.1: "trips x km x Rs/km")
# but no crane-days formula -- crane hire quantity is left to PM judgment
# ("not spelled out anywhere in the document"), same as it treats
# freight's own trip count. Rates are PM-entered here, matching every
# other take-off module in this app (rates are never centrally looked up
# from Master Settings for a raw logistics/material cost -- only %-based
# formula constants live in Settings).
# ---------------------------------------------------------------------------


class FreightCraneTakeoffRequest(BaseModel):
    trips: int | None = Field(default=None, gt=0)
    distance_km: float | None = None  # blank = the project's own distance_km
    rate_per_km: float | None = Field(default=None, gt=0)
    crane_days: int | None = Field(default=None, gt=0)
    crane_day_rate: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _at_least_one_line(self):
        has_freight = self.trips is not None or self.rate_per_km is not None
        if has_freight and (self.trips is None or self.rate_per_km is None):
            raise ValueError("trips and rate_per_km must be given together for a freight line")
        if self.crane_days is not None and self.crane_day_rate is None:
            raise ValueError("crane_day_rate is required when crane_days is given")
        if not has_freight and self.crane_days is None:
            raise ValueError("Provide at least a freight (trips + rate_per_km) or a crane (crane_days + crane_day_rate) line")
        return self


class FreightCraneTakeoffOut(BaseModel):
    breakdown: dict
    lines: list[CostSheetLineOut]


@overheads_router.post(
    "/cost-sheets/{cost_sheet_id}/freight-crane", response_model=FreightCraneTakeoffOut, status_code=201
)
def add_freight_crane_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: FreightCraneTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    """K.1 step 3's freight/crane addition, and B.1's own formula:
    'Freight = trips x km x Rs/km, trips = ceil(total material tonnes /
    truck capacity) by vehicle class.' This app has no per-take-off
    weight/tonnage aggregate to derive trips from automatically, so trips
    (like crane-days) is a PM-entered judgment call, not a computed
    figure -- honestly matching the blueprint's own silence on how many
    crane-days a job needs."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)

    lines_to_create: list[CostSheetLine] = []
    breakdown: dict = {}

    if payload.trips is not None and payload.rate_per_km is not None:
        distance_km = payload.distance_km
        if distance_km is None:
            project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
            distance_km = float(project.distance_km) if project and project.distance_km is not None else None
        if distance_km is None:
            raise HTTPException(
                status_code=422,
                detail="distance_km must be given (the project has no distance_km on file to default to)",
            )
        total_km = payload.trips * distance_km
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.CIVIL,
                category="Site logistics",
                item_name=f"Freight ({payload.trips} trips x {distance_km:g} km)",
                unit="km",
                quantity=round(total_km, 2),
                rate=payload.rate_per_km,
                source=RateSource.MANUAL,
            )
        )
        breakdown["freight_distance_km"] = distance_km
        breakdown["freight_total_km"] = round(total_km, 2)

    if payload.crane_days is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.CIVIL,
                category="Site logistics",
                item_name="Crane hire",
                unit="day",
                quantity=payload.crane_days,
                rate=payload.crane_day_rate,
                source=RateSource.MANUAL,
            )
        )
        breakdown["crane_days"] = payload.crane_days

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return FreightCraneTakeoffOut(breakdown=breakdown, lines=[_line_to_out(line) for line in lines_to_create])


# ---------------------------------------------------------------------------
# K.1 step 4: "+ Design & approvals -- only items NOT already ticked as
# scope lines in step 1 (CAR policy and workmen's compensation insurance
# are priced here and only here)." The structural engineer's own fee is
# already a step-1 scope line (E.5) -- it does not belong here, and this
# endpoint does not duplicate it. No percentage or flat-fee formula is
# given for CAR/workmen's-comp anywhere in the blueprint, so both are
# PM-entered actual premium amounts, exactly as the blueprint's own
# silence implies.
# ---------------------------------------------------------------------------


class DesignApprovalsTakeoffRequest(BaseModel):
    car_policy_premium: float | None = Field(default=None, gt=0)
    workmens_comp_premium: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.car_policy_premium is None and self.workmens_comp_premium is None:
            raise ValueError("Provide at least one of car_policy_premium or workmens_comp_premium")
        return self


class DesignApprovalsTakeoffOut(BaseModel):
    lines: list[CostSheetLineOut]


@overheads_router.post(
    "/cost-sheets/{cost_sheet_id}/design-approvals", response_model=DesignApprovalsTakeoffOut, status_code=201
)
def add_design_approvals_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: DesignApprovalsTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    _get_cost_sheet(db, cost_sheet_id)

    lines_to_create: list[CostSheetLine] = []
    if payload.car_policy_premium is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.SERVICES,
                category="Design & approvals",
                item_name="CAR (Contractor's All Risk) policy",
                unit="set",
                quantity=1,
                rate=payload.car_policy_premium,
                source=RateSource.MANUAL,
            )
        )
    if payload.workmens_comp_premium is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.SERVICES,
                category="Design & approvals",
                item_name="Workmen's compensation insurance",
                unit="set",
                quantity=1,
                rate=payload.workmens_comp_premium,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return DesignApprovalsTakeoffOut(lines=[_line_to_out(line) for line in lines_to_create])


# ---------------------------------------------------------------------------
# K.1 step 4A: "+ Tender overheads (Tender Mode only): BG cost, DLP reserve
# 1% ... BOCW cess 1%, tender fee." DLP reserve % and BOCW cess % are flat
# percentages folded into _compute_cost_sheet_total (documents.py) like
# site establishment/warranty reserve/overhead recovery. BG cost and
# tender fee have no formula that can run automatically from existing
# take-off data (BG cost needs a PM-entered BG amount and bank charge; the
# tender fee is whatever the tender document states) -- both are
# PM-entered actual-amount lines here, same pattern as freight/crane and
# CAR/workmen's-comp above. Never shown as a separate line to the client
# (Part L) is already satisfied: these become ordinary CostSheetLine rows,
# and K.3 keeps the whole cost sheet server-side/PM-Director-only.
# ---------------------------------------------------------------------------


class TenderOverheadsTakeoffRequest(BaseModel):
    tender_fee: float | None = Field(default=None, gt=0)
    bg_amount: float | None = Field(default=None, gt=0)
    bank_charge_percent_pa: float | None = Field(default=None, gt=0)
    contract_weeks: float | None = Field(default=None, gt=0)
    dlp_months: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _at_least_one(self):
        bg_fields = (self.bg_amount, self.bank_charge_percent_pa, self.contract_weeks, self.dlp_months)
        has_bg = any(v is not None for v in bg_fields)
        if has_bg and not all(v is not None for v in bg_fields):
            raise ValueError(
                "bg_amount, bank_charge_percent_pa, contract_weeks and dlp_months must all be given "
                "together for a performance-BG cost line"
            )
        if self.tender_fee is None and not has_bg:
            raise ValueError(
                "Provide at least tender_fee or the BG cost inputs "
                "(bg_amount, bank_charge_percent_pa, contract_weeks, dlp_months)"
            )
        return self


class TenderOverheadsTakeoffOut(BaseModel):
    bg_contract_months: int | None = None
    lines: list[CostSheetLineOut]


@overheads_router.post(
    "/cost-sheets/{cost_sheet_id}/tender-overheads", response_model=TenderOverheadsTakeoffOut, status_code=201
)
def add_tender_overheads_takeoff(
    cost_sheet_id: uuid.UUID,
    payload: TenderOverheadsTakeoffRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*COST_ROLES)),
):
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)
    project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
    if not (project is not None and project.tender_mode):
        raise HTTPException(
            status_code=400,
            detail="Tender overheads only apply to Tender Mode (Government client) projects (Part L)",
        )

    lines_to_create: list[CostSheetLine] = []
    bg_contract_months: int | None = None

    if payload.tender_fee is not None:
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.SERVICES,
                category="Tender overheads",
                item_name="Tender fee",
                unit="set",
                quantity=1,
                rate=payload.tender_fee,
                source=RateSource.MANUAL,
            )
        )

    if payload.bg_amount is not None:
        bg_contract_months, bg_cost = compute_bg_cost(
            payload.bg_amount, payload.bank_charge_percent_pa, payload.contract_weeks, payload.dlp_months
        )
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.SERVICES,
                category="Tender overheads",
                item_name="Performance BG cost",
                unit="set",
                quantity=1,
                rate=bg_cost,
                source=RateSource.MANUAL,
            )
        )

    for line in lines_to_create:
        db.add(line)
    db.commit()
    for line in lines_to_create:
        db.refresh(line)

    return TenderOverheadsTakeoffOut(
        bg_contract_months=bg_contract_months, lines=[_line_to_out(line) for line in lines_to_create]
    )
