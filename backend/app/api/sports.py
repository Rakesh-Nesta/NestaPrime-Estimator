import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import BuildingStatus, Project
from app.models.sport import ProjectSport, Sport, SportCategory

sports_router = APIRouter(prefix="/sports", tags=["sports"])
project_sports_router = APIRouter(prefix="/projects", tags=["project-sports"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("sales", "pm", "director")


class SportOut(BaseModel):
    id: uuid.UUID
    key: str
    display_order: int
    name: str
    category: SportCategory
    playing_dims: str
    build_dims: str
    min_clear_height_ft: float | None
    governing_body: str
    source_citation: str | None

    model_config = ConfigDict(from_attributes=True)


@sports_router.get("", response_model=list[SportOut])
def list_sports(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return db.query(Sport).order_by(Sport.display_order).all()


class ProjectSportCreate(BaseModel):
    sport_id: uuid.UUID
    building_status: BuildingStatus
    number_of_courts: int = 1


class ProjectSportOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    sport_id: uuid.UUID
    building_status: BuildingStatus
    number_of_courts: int
    clear_height_ok: bool = True  # derived; _to_out() sets the real value

    model_config = ConfigDict(from_attributes=True)


def _to_out(project_sport: ProjectSport, sport: Sport, project: Project) -> ProjectSportOut:
    out = ProjectSportOut.model_validate(project_sport)
    out.clear_height_ok = not _violates_min_clear_height(
        sport, project_sport.building_status, project
    )
    return out


def _violates_min_clear_height(
    sport: Sport, building_status: BuildingStatus, project: Project
) -> bool:
    """B.1a: 'Min structure height: building height >= sport min' for
    Existing building / New PEB / Covered shed (Open air has none, '-').
    Phase 1b only captures an actual height value for Existing building
    (B.1 field #14/#15) — PEB and shed heights are chosen later in Part E
    (Structures), not yet built — so only that case can be enforced here."""
    if sport.min_clear_height_ft is None:
        return False
    if building_status != BuildingStatus.EXISTING_BUILDING:
        return False
    if project.existing_building_clear_height_ft is None:
        return False
    return project.existing_building_clear_height_ft < sport.min_clear_height_ft


@project_sports_router.post(
    "/{project_id}/sports", response_model=ProjectSportOut, status_code=201
)
def add_project_sport(
    project_id: uuid.UUID,
    payload: ProjectSportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sport = db.query(Sport).filter(Sport.id == payload.sport_id).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")

    if _violates_min_clear_height(sport, payload.building_status, project):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{sport.name} needs at least {sport.min_clear_height_ft} ft clear height, "
                f"but this building is only {project.existing_building_clear_height_ft} ft (B.1a)"
            ),
        )

    project_sport = ProjectSport(project_id=project_id, **payload.model_dump())
    db.add(project_sport)
    db.commit()
    db.refresh(project_sport)
    return _to_out(project_sport, sport, project)


@project_sports_router.get("/{project_id}/sports", response_model=list[ProjectSportOut])
def list_project_sports(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = db.query(ProjectSport).filter(ProjectSport.project_id == project_id).all()
    sports_by_id = {s.id: s for s in db.query(Sport).all()}
    return [_to_out(row, sports_by_id[row.sport_id], project) for row in rows]


@project_sports_router.delete("/{project_id}/sports/{selection_id}", status_code=204)
def remove_project_sport(
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    row = (
        db.query(ProjectSport)
        .filter(ProjectSport.id == selection_id, ProjectSport.project_id == project_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Sport selection not found")
    db.delete(row)
    db.commit()
