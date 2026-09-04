import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import BuildingStatus, Project, SoilType
from app.models.sport import ProjectSport, Sport, SportCategory

sports_router = APIRouter(prefix="/sports", tags=["sports"])
project_sports_router = APIRouter(prefix="/projects", tags=["project-sports"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("sales", "pm", "director")

# D.2 Base selection matrix — sport groups as given in the table (not every
# one of the 30 sports is covered; uncovered combinations return None rather
# than guessing a composition the blueprint never specified).
_INDOOR_SMOOTH = {"badminton", "table_tennis", "squash", "gymnasium"}
_TURF_FIELD = {"box_cricket", "football_11", "football_7", "football_5_futsal"}
_HARD_COURT = {"tennis", "basketball_outdoor", "pickleball"}
_ATHLETIC_TRACK = {"athletic_track_400m", "athletic_track_200_250m"}
_POOL = {"swimming_pool_25m", "swimming_pool_50m"}


class BaseRecommendation(BaseModel):
    recommended: str
    alternative: str | None
    why: str


def _recommend_base(
    sport: Sport, building_status: BuildingStatus, soil_type: SoilType
) -> BaseRecommendation | None:
    key = sport.key

    if key in _INDOOR_SMOOTH and building_status in (
        BuildingStatus.EXISTING_BUILDING,
        BuildingStatus.NEW_PEB_BUILDING,
    ):
        return BaseRecommendation(recommended="PCC 4-6 in", alternative="RCC 6 in", why="Smooth for wooden/PU")

    if key in _TURF_FIELD and building_status in (BuildingStatus.OPEN_AIR, BuildingStatus.COVERED_SHED):
        if soil_type == SoilType.NORMAL:
            return BaseRecommendation(
                recommended='WBM 8-10 in (+ PCC 4 in box)', alternative=None, why="Drainage for turf life"
            )
        if soil_type == SoilType.ROCKY:
            return BaseRecommendation(recommended="RCC 6 in direct", alternative=None, why="Rock breaking costly")
        if soil_type == SoilType.BLACK_COTTON:
            return BaseRecommendation(
                recommended="Sand layer 6 in + WBM 10 in + geotextile",
                alternative="RCC 6 in",
                why="Swelling soil",
            )
        return None

    if key in _HARD_COURT and building_status == BuildingStatus.OPEN_AIR and soil_type == SoilType.NORMAL:
        return BaseRecommendation(
            recommended="WBM 6 in + Asphalt 3 in", alternative="PCC 6 in", why="Bounce consistency"
        )

    if key in _ATHLETIC_TRACK and building_status == BuildingStatus.OPEN_AIR and soil_type == SoilType.NORMAL:
        return BaseRecommendation(
            recommended="WBM 8 in + Asphalt 2 in", alternative="RCC + asphalt", why="Even surface"
        )

    if key == "padel" and building_status in (BuildingStatus.OPEN_AIR, BuildingStatus.COVERED_SHED):
        return BaseRecommendation(
            recommended="RCC 6 in over WBM 6 in + perimeter beam",
            alternative=None,
            why="Glass post anchoring",
        )

    if key in _POOL:
        return BaseRecommendation(recommended="RCC 8-12 in shell", alternative=None, why="Water load")

    if key == "kids_play_area" and building_status == BuildingStatus.OPEN_AIR and soil_type == SoilType.NORMAL:
        return BaseRecommendation(recommended="WBM 6 in", alternative="PCC 4 in", why="Impact base")

    if key == "beach_volleyball" and building_status == BuildingStatus.OPEN_AIR:
        return BaseRecommendation(
            recommended="Drainage layer + geotextile + 16 in sand",
            alternative=None,
            why="Sand drainage",
        )

    return None


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
    recommended_base: BaseRecommendation | None = None  # derived, D.1/D.2

    model_config = ConfigDict(from_attributes=True)


def _to_out(project_sport: ProjectSport, sport: Sport, project: Project) -> ProjectSportOut:
    out = ProjectSportOut.model_validate(project_sport)
    out.clear_height_ok = not _violates_min_clear_height(
        sport, project_sport.building_status, project
    )
    out.recommended_base = _recommend_base(sport, project_sport.building_status, project.soil_type)
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
