import math
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value
from app.api.sports import _POOL_KEYS, _recommend_base, _recommend_flooring, _recommend_structure
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.project import BuildingStatus, Project
from app.models.sport import ProjectSport, Sport

schedule_router = APIRouter(prefix="/schedule", tags=["schedule"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")

# Fallbacks used only when Part Q's Master Settings has no row yet for the
# key (e.g. a fresh test DB) -- see _get_setting_int below for live values.
MOBILISATION_DAYS_DEFAULT = 5  # N: "3-7 days"
LIGHTING_ELECTRICAL_DAYS_DEFAULT = 4  # N: "3-5 days", runs parallel, never the bottleneck at this size
PEB_DAYS_DEFAULT = 35  # N: "4-6 weeks", midpoint
POOL_DAYS_DEFAULT = 84  # N: "10-14 weeks", midpoint
HANDOVER_DAYS_DEFAULT = 2


def _get_setting_int(db: Session, key: str, default: int) -> int:
    value = get_current_setting_value(db, key)
    return int(value) if value is not None else default


def _get_setting_float(db: Session, key: str, default: float) -> float:
    value = get_current_setting_value(db, key)
    return float(value) if value is not None else default


# N: "e.g. 40% advance, 40% on flooring completion, 20% handover" -- the
# only concrete figures the blueprint gives, for any client type. Q.1
# lists "Payment templates ... Per client type ... Director" as
# configurable, but no client type besides this example ever gets a
# different number in the document -- so every client type defaults to
# this same 40/40/20 split until a Director actually configures a
# different one for that specific client_type via Master Settings.
PAYMENT_SCHEDULE_PERCENT_DEFAULT = {"advance": 40.0, "milestone": 40.0, "handover": 20.0}

# N: curing days keyed to (base type, flooring type) -- both are text we
# generate ourselves in D.2/F.1-F.2's own vocabulary, so keyword matching
# on them is reliable, not free-text parsing.
_CURING_DAYS_TABLE = [
    ("turf", "wbm", 0),
    ("turf", "pcc", 7),
    ("acrylic", "asphalt", 14),
    ("pu", "asphalt", 14),
    ("acrylic", "pcc", 28),
    ("pu", "pcc", 28),
    ("wooden", "pcc", 28),
    ("tiles", "rcc", 14),
]


def _curing_days(base_text: str | None, flooring_text: str | None) -> int | None:
    if not base_text or not flooring_text:
        return None
    base_lower = base_text.lower()
    flooring_lower = flooring_text.lower()
    for flooring_kw, base_kw, days in _CURING_DAYS_TABLE:
        if flooring_kw in flooring_lower and base_kw in base_lower:
            return days
    return None


def _flooring_lay_days(area_sqft: float, flooring_text: str | None) -> int | None:
    if not flooring_text:
        return None
    text = flooring_text.lower()
    if "turf" in text:
        return math.ceil(area_sqft / 2500)
    if "wooden" in text:
        return math.ceil(area_sqft / 800)
    if "acrylic" in text:
        return 9  # N: "acrylic 8-10 days (coats)", midpoint
    return None


class ScheduleActivity(BaseModel):
    name: str
    start_day: int
    duration_days: int
    end_day: int
    start_date: date
    end_date: date
    parallel: bool = False  # doesn't extend the critical path
    note: str | None = None


class PaymentMilestone(BaseModel):
    name: str
    percent: float
    date: date


class ScheduleOut(BaseModel):
    total_days: int
    total_weeks: int
    activities: list[ScheduleActivity]
    payment_schedule: list[PaymentMilestone]


@schedule_router.get("/project-sports/{project_sport_id}", response_model=ScheduleOut)
def get_schedule(
    project_sport_id: uuid.UUID,
    start_date: date | None = None,
    mobilisation_days: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    """Part N: activity durations keyed to the sport's own build area and
    its D.2/E.4/F.1-F.2 recommendations, chained into a single critical
    path (Mobilisation -> Base+curing -> [Erection] -> Flooring ->
    Handover, or a lump PEB/Pool activity in place of Base/Erection/
    Flooring). Lighting & electrical runs parallel and is listed but never
    extends the path at this size (N: 3-5 days). MS fabrication (E.2, off-
    site, 1 day/800 kg) needs real steel kg from a take-off that doesn't
    exist yet, so it's omitted rather than guessed -- it runs off-site in
    parallel with Base regardless, so omitting it never understates the
    critical path.

    Sequencing choices not pinned down by the blueprint (erection vs.
    flooring order; which activity 'parallel' lighting sits beside) are
    judgment calls made explicitly here, not blueprint-given facts."""
    project_sport = db.query(ProjectSport).filter(ProjectSport.id == project_sport_id).first()
    if not project_sport:
        raise HTTPException(status_code=404, detail="Sport selection not found")
    sport = db.query(Sport).filter(Sport.id == project_sport.sport_id).first()
    project = db.query(Project).filter(Project.id == project_sport.project_id).first()
    client = db.query(Client).filter(Client.id == project.client_id).first()

    start = start_date or date.today()
    resolved_mobilisation_days = (
        mobilisation_days
        if mobilisation_days is not None
        else _get_setting_int(db, "schedule_mobilisation_days_default", MOBILISATION_DAYS_DEFAULT)
    )
    lighting_electrical_days = _get_setting_int(
        db, "schedule_lighting_electrical_days", LIGHTING_ELECTRICAL_DAYS_DEFAULT
    )
    peb_days = _get_setting_int(db, "schedule_peb_days", PEB_DAYS_DEFAULT)
    pool_days = _get_setting_int(db, "schedule_pool_days", POOL_DAYS_DEFAULT)
    handover_days = _get_setting_int(db, "schedule_handover_days", HANDOVER_DAYS_DEFAULT)

    activities: list[ScheduleActivity] = []
    cursor = 0

    def add(name: str, duration: int, note: str | None = None, parallel: bool = False) -> None:
        nonlocal cursor
        activity_start = cursor
        activity_end = cursor if parallel else cursor + duration
        activities.append(
            ScheduleActivity(
                name=name,
                start_day=activity_start,
                duration_days=duration,
                end_day=activity_start + duration,
                start_date=start + timedelta(days=activity_start),
                end_date=start + timedelta(days=activity_start + duration),
                parallel=parallel,
                note=note,
            )
        )
        if not parallel:
            cursor = activity_end

    add("Mobilisation & site prep", resolved_mobilisation_days)

    area_sqft = None
    if sport.build_l_ft is not None and sport.build_w_ft is not None:
        area_sqft = float(sport.build_l_ft) * float(sport.build_w_ft) * project_sport.number_of_courts

    is_pool = sport.key in _POOL_KEYS
    is_peb = project_sport.building_status == BuildingStatus.NEW_PEB_BUILDING

    base = _recommend_base(sport, project_sport.building_status, project.soil_type)
    structure = _recommend_structure(sport, project_sport.building_status, project.package)
    flooring = _recommend_flooring(sport, project.package)
    flooring_text = flooring.selected if flooring else None

    flooring_complete_day = None

    if is_pool:
        add("Pool construction", pool_days, note="N: 10-14 weeks, midpoint")
        flooring_complete_day = cursor
    elif is_peb:
        add("PEB construction", peb_days, note="N: 4-6 weeks, midpoint")
        if area_sqft is not None and flooring_text:
            lay_days = _flooring_lay_days(area_sqft, flooring_text)
            if lay_days is not None:
                add(f"Flooring ({flooring_text})", lay_days)
        flooring_complete_day = cursor
    else:
        if area_sqft is not None:
            base_days = math.ceil(area_sqft / 1500)
            curing = _curing_days(base.recommended if base else None, flooring_text)
            add(
                f"Base ({base.recommended if base else 'not yet in D.2 matrix'})",
                base_days + (curing or 0),
                note=None if curing is not None else "curing days not in N's table for this base/flooring pair",
            )

            if structure is not None:
                erection_days = math.ceil(area_sqft / 1000)
                add(f"Structure erection & netting (Type {structure.structure_type})", erection_days)

            lay_days = _flooring_lay_days(area_sqft, flooring_text) if flooring_text else None
            if lay_days is not None:
                add(f"Flooring ({flooring_text})", lay_days)
            flooring_complete_day = cursor
        else:
            flooring_complete_day = cursor

    add(
        "Lighting & electrical",
        lighting_electrical_days,
        note="N: parallel, 3-5 days -- listed but not on the critical path at this size",
        parallel=True,
    )

    add("Handover & testing", handover_days)

    total_days = cursor
    total_weeks = math.ceil(total_days / 7)

    # N: "e.g. 40% advance, 40% on flooring completion, 20% handover" --
    # Q.1: "Payment templates ... per client type ... Director"
    # configurable. The milestone structure (three stages tied to this
    # schedule's own mobilisation/flooring-completion/handover days) is
    # fixed -- the blueprint gives no alternative milestone breakdown for
    # any client type -- but each stage's percentage is looked up per the
    # client's own type, defaulting to the blueprint's own 40/40/20 until
    # a Director configures a different split for that client type.
    client_type_key = client.type.value if client is not None else "unknown"
    advance_percent = _get_setting_float(
        db, f"payment_schedule_advance_percent_{client_type_key}", PAYMENT_SCHEDULE_PERCENT_DEFAULT["advance"]
    )
    milestone_percent = _get_setting_float(
        db, f"payment_schedule_milestone_percent_{client_type_key}", PAYMENT_SCHEDULE_PERCENT_DEFAULT["milestone"]
    )
    handover_percent = _get_setting_float(
        db, f"payment_schedule_handover_percent_{client_type_key}", PAYMENT_SCHEDULE_PERCENT_DEFAULT["handover"]
    )
    payment_schedule = [
        PaymentMilestone(name="Advance", percent=advance_percent, date=start),
        PaymentMilestone(
            name="Flooring completion",
            percent=milestone_percent,
            date=start + timedelta(days=flooring_complete_day or total_days),
        ),
        PaymentMilestone(name="Handover", percent=handover_percent, date=start + timedelta(days=total_days)),
    ]

    return ScheduleOut(
        total_days=total_days,
        total_weeks=total_weeks,
        activities=activities,
        payment_schedule=payment_schedule,
    )
