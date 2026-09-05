import math
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.sports import _POOL_KEYS, _recommend_base, _recommend_flooring, _recommend_structure
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import BuildingStatus, Project
from app.models.sport import ProjectSport, Sport

schedule_router = APIRouter(prefix="/schedule", tags=["schedule"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")

MOBILISATION_DAYS_DEFAULT = 5  # N: "3-7 days"
LIGHTING_ELECTRICAL_DAYS = 4  # N: "3-5 days", runs parallel, never the bottleneck at this size
PEB_DAYS = 35  # N: "4-6 weeks", midpoint
POOL_DAYS = 84  # N: "10-14 weeks", midpoint
HANDOVER_DAYS = 2

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
    mobilisation_days: int = MOBILISATION_DAYS_DEFAULT,
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

    start = start_date or date.today()
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

    add("Mobilisation & site prep", mobilisation_days)

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
        add("Pool construction", POOL_DAYS, note="N: 10-14 weeks, midpoint")
        flooring_complete_day = cursor
    elif is_peb:
        add("PEB construction", PEB_DAYS, note="N: 4-6 weeks, midpoint")
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
        LIGHTING_ELECTRICAL_DAYS,
        note="N: parallel, 3-5 days -- listed but not on the critical path at this size",
        parallel=True,
    )

    add("Handover & testing", HANDOVER_DAYS)

    total_days = cursor
    total_weeks = math.ceil(total_days / 7)

    # N: "e.g. 40% advance, 40% on flooring completion, 20% handover"
    payment_schedule = [
        PaymentMilestone(name="Advance", percent=40.0, date=start),
        PaymentMilestone(
            name="Flooring completion",
            percent=40.0,
            date=start + timedelta(days=flooring_complete_day or total_days),
        ),
        PaymentMilestone(name="Handover", percent=20.0, date=start + timedelta(days=total_days)),
    ]

    return ScheduleOut(
        total_days=total_days,
        total_weeks=total_weeks,
        activities=activities,
        payment_schedule=payment_schedule,
    )
