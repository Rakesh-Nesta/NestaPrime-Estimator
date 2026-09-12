import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.clients import _default_package
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client, ClientType
from app.models.hub import Hub
from app.models.project import (
    BuildingStatus,
    Package,
    PowerAvailable,
    Project,
    ProjectType,
    SiteAccess,
    SiteCondition,
    SoilType,
    UnitSystem,
)

router = APIRouter(prefix="/projects", tags=["projects"])

# D.4: soil test (and so safe_bearing_capacity) is mandatory for these
# combinations before a real build proceeds — enforced here as a warning
# field on the response, not a hard block, since Phase 1a has no soil-report
# upload flow yet to attach as evidence.
SBC_MANDATORY_SOILS = {SoilType.ROCKY, SoilType.BLACK_COTTON, SoilType.FILLED}


def _generate_project_no(db: Session) -> str:
    """P-YYMM-#### (M.2 rule 10) — one number shared later by the Cost
    Sheet, Estimate and Quotation records once those exist."""
    yymm = datetime.now(UTC).strftime("%y%m")
    prefix = f"P-{yymm}-"
    existing = (
        db.query(Project.project_no)
        .filter(Project.project_no.like(f"{prefix}%"))
        .all()
    )
    max_seq = 0
    for (project_no,) in existing:
        try:
            max_seq = max(max_seq, int(project_no.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}{max_seq + 1:04d}"


class ProjectCreate(BaseModel):
    client_id: uuid.UUID
    project_type: ProjectType = ProjectType.NEW_BUILD
    city: str
    site_address: str | None = None
    site_state_code: str | None = None
    hub_id: uuid.UUID | None = None
    # Bounds match each column's actual NUMERIC(precision, scale) on the
    # Project model -- without these, a value the column can't hold
    # (e.g. distance_km > 99999.9) reaches Postgres and raises an
    # unhandled NumericValueOutOfRange (a raw 500), instead of the
    # friendly 422 a bad form value should produce.
    distance_km: float | None = Field(default=None, ge=0, le=99999.9)
    site_condition: SiteCondition
    soil_type: SoilType
    building_status: BuildingStatus
    site_access: SiteAccess
    power_available: PowerAvailable
    water_available: bool
    number_of_courts: int = 1
    unit_system: UnitSystem = UnitSystem.FEET
    # B.2: left blank, this resolves from the client's type default
    # (_default_package) at creation time -- explicit still wins.
    package: Package | None = None
    safe_bearing_capacity: float | None = Field(default=None, ge=0, le=999999.99)
    existing_building_clear_height_ft: float | None = Field(default=None, ge=0, le=9999.99)


class ProjectOut(BaseModel):
    id: uuid.UUID
    project_no: str
    client_id: uuid.UUID
    project_type: ProjectType
    city: str
    site_address: str | None
    hub_id: uuid.UUID | None
    distance_km: float | None
    site_condition: SiteCondition
    soil_type: SoilType
    building_status: BuildingStatus
    site_access: SiteAccess
    power_available: PowerAvailable
    water_available: bool
    number_of_courts: int
    unit_system: UnitSystem
    package: Package
    safe_bearing_capacity: float | None
    existing_building_clear_height_ft: float | None
    tender_mode: bool
    soil_test_required: bool = False  # derived, not stored — D.4; _to_out() sets the real value

    # D.4 site-prep triggers (B.2's worked examples), all derived — none
    # stored, all recomputed by _to_out() on every read.
    rock_breaking_required: bool = False
    dewatering_required: bool = False
    sand_cns_layer_required: bool = False

    model_config = ConfigDict(from_attributes=True)


def _to_out(project: Project) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    out.soil_test_required = (
        project.soil_type in SBC_MANDATORY_SOILS
        or project.building_status == BuildingStatus.NEW_PEB_BUILDING
        or project.site_condition == SiteCondition.WATER_LOGGED
    )
    # D.4 / B.2: Soil = Rocky -> rock-breaking; Soil = Black cotton ->
    # sand-filling + CNS layer; Site = Water-logged -> dewatering.
    out.rock_breaking_required = project.soil_type == SoilType.ROCKY
    out.dewatering_required = project.site_condition == SiteCondition.WATER_LOGGED
    out.sand_cns_layer_required = project.soil_type == SoilType.BLACK_COTTON
    return out


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.hub_id is not None and not db.query(Hub).filter(Hub.id == payload.hub_id).first():
        raise HTTPException(status_code=404, detail="Hub not found")

    if (
        payload.existing_building_clear_height_ft is not None
        and payload.building_status != BuildingStatus.EXISTING_BUILDING
    ):
        raise HTTPException(
            status_code=400,
            detail="existing_building_clear_height_ft only applies when building_status is existing_building",
        )

    # B.2: "Client = School -> Package Standard" -- resolved from the
    # client's type when not given explicitly; not every client type has
    # a configured default, so an unresolved one asks for an explicit
    # choice rather than silently picking something the blueprint never
    # specified for that type.
    package = payload.package
    if package is None:
        package = _default_package(db, client.type)
        if package is None:
            raise HTTPException(
                status_code=422,
                detail=f"No default package configured for client type '{client.type.value}' -- specify package",
            )

    project = Project(
        project_no=_generate_project_no(db),
        # B.2: Client = Government auto-switches Tender Mode on — not a
        # user-settable field, derived here at creation time.
        tender_mode=(client.type == ClientType.GOVERNMENT),
        package=package,
        **payload.model_dump(exclude={"package"}),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director", "procurement", "site_engineer")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_out(project)
