import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.clients import _default_package
from app.api.field_settings import get_field_state
from app.core.auth import require_roles
from app.core.db_retry import create_with_retry
from app.db.session import get_db
from app.models.client import Client, ClientType
from app.models.document import Quotation, QuotationStatus
from app.models.hub import Hub
from app.models.opportunity import Opportunity, OpportunityStage
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
    # Amendment 5 Phase 2: these three can be omitted when a Director has
    # marked the field Optional or Hidden on New Project Setup (see
    # app/api/field_settings.py) -- create_project() below still 422s if
    # one is missing while its own field-setting says Compulsory
    # (today's default for all three, unchanged unless a Director opts
    # one down), so the *effective* requiredness is enforced there, not
    # by this schema alone.
    soil_type: SoilType | None = None
    building_status: BuildingStatus
    site_access: SiteAccess | None = None
    power_available: PowerAvailable | None = None
    water_available: bool | None = None
    number_of_courts: int = 1
    unit_system: UnitSystem = UnitSystem.FEET
    # B.2: left blank, this resolves from the client's type default
    # (_default_package) at creation time -- explicit still wins.
    package: Package | None = None
    safe_bearing_capacity: float | None = Field(default=None, ge=0, le=999999.99)
    existing_building_clear_height_ft: float | None = Field(default=None, ge=0, le=9999.99)
    # Amendment 2: true only for a project created through the 5-field
    # Quick setup form -- every field above the frontend didn't ask for
    # in that flow was filled with a stated assumption. Read back by
    # pdf_documents.py to print those assumptions as T&C clauses on the
    # Quotation PDF.
    quick_setup: bool = False
    # Amendment 28 Part B: marks validation/demo data at creation time --
    # same role gate as the rest of this endpoint (Director-only
    # flagging of an *existing* project is a separate, dedicated PATCH
    # below, since backfilling a project created before this flag existed
    # needs no new Project data, just this one field).
    is_calibration: bool = False
    # Amendment 44 Phase C (Section E step 5): set only when reached via
    # "Start Project" on a Won, Client-linked Opportunity -- validated in
    # create_project() below, null for every other creation path.
    opportunity_id: uuid.UUID | None = None


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
    soil_type: SoilType | None
    building_status: BuildingStatus
    site_access: SiteAccess | None
    power_available: PowerAvailable | None
    water_available: bool | None
    number_of_courts: int
    unit_system: UnitSystem
    package: Package
    quick_setup: bool
    custom_notes: str | None
    safe_bearing_capacity: float | None
    existing_building_clear_height_ft: float | None
    tender_mode: bool
    is_calibration: bool
    opportunity_id: uuid.UUID | None
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

    # Amendment 44 Phase C: validated up front so a rejected hand-off never
    # leaves an orphan Project behind. Only a Won Opportunity already
    # linked to *this* Client, and not already converted, may start one.
    opportunity = None
    if payload.opportunity_id is not None:
        opportunity = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        if opportunity.stage != OpportunityStage.WON:
            raise HTTPException(status_code=400, detail="Only a Won Opportunity can start a Project")
        if opportunity.client_id != payload.client_id:
            raise HTTPException(
                status_code=400,
                detail="The Opportunity must be linked to this Client before it can start a Project",
            )
        if opportunity.project_id is not None:
            raise HTTPException(status_code=400, detail="This Opportunity has already started a Project")

    # Amendment 5 Phase 2 (Section 6, extended by Section 22):
    # soil_type/site_access/power_available/water_available are the four
    # governed fields this app can actually block on (distance_km/
    # number_of_courts are already nullable/defaulted, so a field-setting
    # only affects whether New Project Setup shows them, not whether the
    # API accepts their absence). A field with no FieldSetting row is
    # COMPULSORY -- today's real behavior, unchanged until a Director
    # opts it down.
    for field_key, value in (
        ("soil_type", payload.soil_type),
        ("site_access", payload.site_access),
        ("power_available", payload.power_available),
        ("water_available", payload.water_available),
    ):
        if value is None and get_field_state(db, field_key) == "compulsory":
            raise HTTPException(status_code=422, detail=f"'{field_key}' is required")

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

    def _build_project() -> Project:
        # Amendment 23: called fresh on every retry attempt so a
        # collision re-reads the now-updated row set and computes a
        # genuinely new project_no, rather than retrying with the same
        # doomed-to-collide value.
        project = Project(
            project_no=_generate_project_no(db),
            # B.2: Client = Government auto-switches Tender Mode on — not a
            # user-settable field, derived here at creation time.
            tender_mode=(client.type == ClientType.GOVERNMENT),
            package=package,
            **payload.model_dump(exclude={"package"}),
        )
        db.add(project)
        return project

    project = create_with_retry(db, _build_project)
    if opportunity is not None:
        opportunity.project_id = project.id
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


class ProjectSummaryOut(BaseModel):
    """Amendment 12 (Section 11): the Dashboard's 'Open Projects' /
    'Quotation-winning projects' tiles had no screen behind them at all --
    only a 5-row 'Recent projects' list. status here mirrors dashboard.py's
    own open/won/lost vocabulary exactly, so a drill-down's count matches
    what the tile itself showed."""

    id: uuid.UUID
    project_no: str
    client_name: str
    city: str
    status: str  # "open" | "won" | "lost"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Amendment 53 (Section 57): the read gate for the project list, named so the global
# quick search reuses exactly it instead of copying the tuple.
LIST_ROLES = ("sales", "pm", "director", "procurement", "site_engineer", "ca_tax")


@router.get("", response_model=list[ProjectSummaryOut])
def list_projects(
    search: str | None = None,
    status: str | None = None,  # "open" | "won" | "lost"
    client_id: uuid.UUID | None = None,  # Section 19: per-client project list
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LIST_ROLES)),
):
    won_project_ids = (
        db.query(Quotation.project_id).filter(Quotation.status == QuotationStatus.WON).distinct()
    )
    lost_project_ids = (
        db.query(Quotation.project_id).filter(Quotation.status == QuotationStatus.LOST).distinct()
    )
    closed_project_ids = (
        db.query(Quotation.project_id)
        .filter(Quotation.status.in_([QuotationStatus.WON, QuotationStatus.LOST]))
        .distinct()
    )

    query = db.query(Project, Client.name).join(Client, Client.id == Project.client_id)
    if client_id is not None:
        query = query.filter(Project.client_id == client_id)
    if search:
        needle = f"%{search}%"
        query = query.filter(
            (Project.project_no.ilike(needle)) | (Client.name.ilike(needle))
        )
    if status == "open":
        query = query.filter(~Project.id.in_(closed_project_ids))
    elif status == "won":
        query = query.filter(Project.id.in_(won_project_ids))
    elif status == "lost":
        query = query.filter(Project.id.in_(lost_project_ids))

    rows = query.order_by(Project.created_at.desc()).all()
    won_ids = {pid for (pid,) in won_project_ids.all()}
    lost_ids = {pid for (pid,) in lost_project_ids.all()}

    out = []
    for project, client_name in rows:
        if project.id in won_ids:
            row_status = "won"
        elif project.id in lost_ids:
            row_status = "lost"
        else:
            row_status = "open"
        out.append(
            ProjectSummaryOut(
                id=project.id,
                project_no=project.project_no,
                client_name=client_name,
                city=project.city,
                status=row_status,
                created_at=project.created_at,
            )
        )
    return out


class ProjectNotesUpdate(BaseModel):
    custom_notes: str | None = None


@router.patch("/{project_id}/notes", response_model=ProjectOut)
def update_project_notes(
    project_id: uuid.UUID,
    payload: ProjectNotesUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("sales", "pm", "director")),
):
    """Amendment 5's Custom Notes component -- one note per PROJECT, not
    per screen: the same "+ Add Note" button on Project Setup, Cost Sheet,
    and Estimate all read/write this single field, so a note added on one
    screen is visible from the other two."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.custom_notes = payload.custom_notes
    db.commit()
    db.refresh(project)
    return _to_out(project)


class ProjectCalibrationUpdate(BaseModel):
    is_calibration: bool


@router.patch("/{project_id}/calibration", response_model=ProjectOut)
def update_project_calibration_flag(
    project_id: uuid.UUID,
    payload: ProjectCalibrationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("director")),
):
    """Amendment 28 Part B: flagging an *existing* project (e.g. a manual
    Note R1 Mathura/Noida/Bathinda backfill, since there's no reliable
    code-level signal to detect those automatically) is Director-only,
    unlike setting the flag at creation time on ProjectCreate above."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_calibration = payload.is_calibration
    db.commit()
    db.refresh(project)
    return _to_out(project)
