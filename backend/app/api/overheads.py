import math
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.api.documents import CostSheetLineOut, _line_to_out
from app.api.site_works import _get_cost_sheet
from app.api.tender import compute_bg_cost
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.document import CostSheetLine, WorkPackage
from app.models.project import Project
from app.models.rate_item import RateSource
from app.models.vehicle_class import VehicleClass

overheads_router = APIRouter(tags=["overheads"])
vehicle_classes_router = APIRouter(prefix="/vehicle-classes", tags=["vehicle-classes"])

COST_ROLES = ("pm", "director")
# Same footing as RateItem/NettingGrade -- real cost-side Rs/km and
# capacity data (K.3), reads open to whoever might build a Cost Sheet.
VEHICLE_CLASS_READ_ROLES = ("pm", "director", "procurement", "site_engineer")
# Q.1: "Global | Director" -- Master Settings ownership, same as every
# other Director-only catalog this session (netting grades, accessories).
VEHICLE_CLASS_WRITE_ROLES = ("director",)


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
    # Either given directly (a one-off manual freight line), or derived
    # from total_material_tonnes + vehicle_class_id below -- B.1's own
    # formula, "trips = ceil(total material tonnes / truck capacity)".
    # An explicit trips/rate_per_km alongside a vehicle_class_id overrides
    # what that class would otherwise compute, same escape hatch as every
    # other catalog-with-manual-override this codebase uses (netting
    # grades, accessory catalog).
    trips: int | None = Field(default=None, gt=0)
    total_material_tonnes: float | None = Field(default=None, gt=0)
    vehicle_class_id: uuid.UUID | None = None
    distance_km: float | None = None  # blank = the project's own distance_km
    rate_per_km: float | None = Field(default=None, gt=0)
    crane_days: int | None = Field(default=None, gt=0)
    crane_day_rate: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _at_least_one_line(self):
        if self.total_material_tonnes is not None and self.vehicle_class_id is None:
            raise ValueError("vehicle_class_id is required when total_material_tonnes is given")
        can_derive_trips = self.total_material_tonnes is not None and self.vehicle_class_id is not None
        has_rate = self.rate_per_km is not None or self.vehicle_class_id is not None
        has_trips = self.trips is not None or can_derive_trips
        has_freight = has_rate or has_trips
        if has_freight and not (has_rate and has_trips):
            raise ValueError(
                "A freight line needs a rate (rate_per_km or vehicle_class_id) and trips (trips, or "
                "total_material_tonnes + vehicle_class_id to derive it)"
            )
        if self.crane_days is not None and self.crane_day_rate is None:
            raise ValueError("crane_day_rate is required when crane_days is given")
        if not has_freight and self.crane_days is None:
            raise ValueError("Provide at least a freight line or a crane (crane_days + crane_day_rate) line")
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
    weight/tonnage aggregate to derive tonnage from automatically (lines
    are mixed units -- kg, sqm, cum -- with no density table for most
    materials), so total_material_tonnes is still a PM-entered figure,
    same honesty as crane-days. But once that figure is entered alongside
    a selected VehicleClass, B.1's own ceil(tonnes/capacity) formula and
    that class's Rs/km rate ARE computed here rather than PM-guessed --
    the part of the formula the blueprint actually specifies."""
    cost_sheet = _get_cost_sheet(db, cost_sheet_id)

    lines_to_create: list[CostSheetLine] = []
    breakdown: dict = {}

    vehicle_class = None
    if payload.vehicle_class_id is not None:
        vehicle_class = db.query(VehicleClass).filter(VehicleClass.id == payload.vehicle_class_id).first()
        if not vehicle_class:
            raise HTTPException(status_code=404, detail="Vehicle class not found")

    rate_per_km = payload.rate_per_km if payload.rate_per_km is not None else (
        float(vehicle_class.rate_per_km) if vehicle_class else None
    )
    trips = payload.trips
    if trips is None and vehicle_class is not None and payload.total_material_tonnes is not None:
        trips = math.ceil(payload.total_material_tonnes / float(vehicle_class.truck_capacity_tonnes))

    if trips is not None and rate_per_km is not None:
        distance_km = payload.distance_km
        if distance_km is None:
            project = db.query(Project).filter(Project.id == cost_sheet.project_id).first()
            distance_km = float(project.distance_km) if project and project.distance_km is not None else None
        if distance_km is None:
            raise HTTPException(
                status_code=422,
                detail="distance_km must be given (the project has no distance_km on file to default to)",
            )
        total_km = trips * distance_km
        item_name = f"Freight ({trips} trips x {distance_km:g} km)"
        if vehicle_class is not None:
            item_name += f" -- {vehicle_class.name}"
        lines_to_create.append(
            CostSheetLine(
                cost_sheet_id=cost_sheet_id,
                work_package=WorkPackage.CIVIL,
                category="Site logistics",
                item_name=item_name,
                unit="km",
                quantity=round(total_km, 2),
                rate=rate_per_km,
                source=RateSource.MANUAL,
            )
        )
        breakdown["freight_trips"] = trips
        breakdown["freight_distance_km"] = distance_km
        breakdown["freight_total_km"] = round(total_km, 2)
        breakdown["freight_vehicle_class"] = vehicle_class.name if vehicle_class else None

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


# --------------------------------------------------------------------------
# Q.1 vehicle class catalog -- Director-editable, empty by default (no
# worked example anywhere in the blueprint to seed from, unlike E.3's
# netting grades or B.2's warranty years).
# --------------------------------------------------------------------------


class VehicleClassOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    truck_capacity_tonnes: float
    rate_per_km: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@vehicle_classes_router.get("", response_model=list[VehicleClassOut])
def list_vehicle_classes(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VEHICLE_CLASS_READ_ROLES)),
):
    query = db.query(VehicleClass)
    if not include_inactive:
        query = query.filter(VehicleClass.is_active.is_(True))
    return query.order_by(VehicleClass.key).all()


class VehicleClassCreate(BaseModel):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    truck_capacity_tonnes: float = Field(gt=0)
    rate_per_km: float = Field(gt=0)


class VehicleClassUpdate(BaseModel):
    name: str | None = None
    truck_capacity_tonnes: float | None = Field(default=None, gt=0)
    rate_per_km: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


@vehicle_classes_router.post("", response_model=VehicleClassOut, status_code=201)
def create_vehicle_class(
    payload: VehicleClassCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VEHICLE_CLASS_WRITE_ROLES)),
):
    if db.query(VehicleClass).filter(VehicleClass.key == payload.key).first():
        raise HTTPException(status_code=409, detail=f"Vehicle class '{payload.key}' already exists")
    vehicle_class = VehicleClass(**payload.model_dump())
    db.add(vehicle_class)
    db.commit()
    db.refresh(vehicle_class)
    return vehicle_class


@vehicle_classes_router.patch("/{vehicle_class_id}", response_model=VehicleClassOut)
def update_vehicle_class(
    vehicle_class_id: uuid.UUID,
    payload: VehicleClassUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VEHICLE_CLASS_WRITE_ROLES)),
):
    vehicle_class = db.query(VehicleClass).filter(VehicleClass.id == vehicle_class_id).first()
    if not vehicle_class:
        raise HTTPException(status_code=404, detail="Vehicle class not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle_class, field, value)
    db.commit()
    db.refresh(vehicle_class)
    return vehicle_class
