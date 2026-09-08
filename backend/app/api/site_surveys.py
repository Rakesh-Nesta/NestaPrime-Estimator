import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentTag
from app.models.project import Project, SiteCondition, SoilType, UnitSystem
from app.models.setting import DocumentType
from app.models.site_survey import SiteSurvey, SiteSurveyStatus

site_surveys_router = APIRouter(tags=["site-surveys"])

# A.3: "Site Engineer: Site survey form, actuals entry" -- Sales,
# Procurement and CA/Tax have no reason to write a site survey; PM/
# Director oversee (M.7.1's recipient row: "-> PM").
ROLES = ("site_engineer", "pm", "director")

# Appendix C: "photos (min 4)".
MIN_PHOTOS_TO_COMPLETE = 4


class SiteSurveyCreate(BaseModel):
    client_name: str | None = None
    site_address: str | None = None
    pin_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None


class SiteSurveyUpdate(BaseModel):
    """Every Appendix C field except project_id/status -- all optional so
    the form can be filled in progressively (M.7.1: "blank / filled")."""

    client_name: str | None = None
    site_address: str | None = None
    pin_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    sports_and_count: str | None = None
    available_area_length: float | None = None
    available_area_width: float | None = None
    area_unit: UnitSystem | None = None
    slope_or_level: SiteCondition | None = None
    soil_observed: SoilType | None = None
    water_logging_observed: bool | None = None
    access_road_width_m: float | None = None
    crane_access: bool | None = None
    power_phase: str | None = None
    power_load_kw: float | None = None
    water_source: str | None = None
    existing_structures_trees: str | None = None
    neighbour_constraints: str | None = None
    orientation: str | None = None
    surveyed_at: date | None = None


class SiteSurveyOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: SiteSurveyStatus
    client_name: str | None
    site_address: str | None
    pin_code: str | None
    contact_name: str | None
    contact_phone: str | None
    sports_and_count: str | None
    available_area_length: float | None
    available_area_width: float | None
    area_unit: UnitSystem | None
    slope_or_level: SiteCondition | None
    soil_observed: SoilType | None
    water_logging_observed: bool | None
    access_road_width_m: float | None
    crane_access: bool | None
    power_phase: str | None
    power_load_kw: float | None
    water_source: str | None
    existing_structures_trees: str | None
    neighbour_constraints: str | None
    orientation: str | None
    surveyed_by_id: uuid.UUID | None
    surveyed_at: date | None
    created_by_id: uuid.UUID
    created_at: datetime
    completed_at: datetime | None
    photo_count: int = 0

    model_config = ConfigDict(from_attributes=True)


def _photo_count(db: Session, site_survey_id: uuid.UUID) -> int:
    return (
        db.query(Attachment)
        .filter(
            Attachment.doc_type == DocumentType.SITE_SURVEY,
            Attachment.doc_id == site_survey_id,
            Attachment.tag == AttachmentTag.PHOTO,
            Attachment.superseded_by_id.is_(None),
        )
        .count()
    )


def _to_out(db: Session, survey: SiteSurvey) -> SiteSurveyOut:
    out = SiteSurveyOut.model_validate(survey)
    out.photo_count = _photo_count(db, survey.id)
    return out


@site_surveys_router.post("/projects/{project_id}/site-surveys", response_model=SiteSurveyOut, status_code=201)
def create_site_survey(
    project_id: uuid.UUID,
    payload: SiteSurveyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """Appendix C / M.7.1: 'Site survey form (blank / filled)' -- starts
    blank (Draft), the Site Engineer fills it in over the course of the
    site visit via PATCH, then marks it Completed once done."""
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")

    survey = SiteSurvey(
        project_id=project_id,
        status=SiteSurveyStatus.DRAFT,
        client_name=payload.client_name,
        site_address=payload.site_address,
        pin_code=payload.pin_code,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        created_by_id=current_user.id,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return _to_out(db, survey)


@site_surveys_router.get("/projects/{project_id}/site-surveys", response_model=list[SiteSurveyOut])
def list_site_surveys(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    rows = (
        db.query(SiteSurvey)
        .filter(SiteSurvey.project_id == project_id)
        .order_by(SiteSurvey.created_at.desc())
        .all()
    )
    return [_to_out(db, r) for r in rows]


@site_surveys_router.get("/site-surveys/{site_survey_id}", response_model=SiteSurveyOut)
def get_site_survey(
    site_survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == site_survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Site survey not found")
    return _to_out(db, survey)


@site_surveys_router.patch("/site-surveys/{site_survey_id}", response_model=SiteSurveyOut)
def update_site_survey(
    site_survey_id: uuid.UUID,
    payload: SiteSurveyUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == site_survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Site survey not found")
    if survey.status == SiteSurveyStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot edit a completed site survey")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(survey, field, value)
    db.commit()
    db.refresh(survey)
    return _to_out(db, survey)


@site_surveys_router.post("/site-surveys/{site_survey_id}/complete", response_model=SiteSurveyOut)
def complete_site_survey(
    site_survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """Appendix C: 'photos (min 4) . surveyor & date' -- both are treated
    as the completion gate, not merely optional fields: a survey with
    fewer than 4 photos, or no surveyed_at set, cannot be marked
    Completed. surveyed_by defaults to whoever completes it."""
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == site_survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Site survey not found")
    if survey.status == SiteSurveyStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Site survey is already completed")

    photo_count = _photo_count(db, site_survey_id)
    if photo_count < MIN_PHOTOS_TO_COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"At least {MIN_PHOTOS_TO_COMPLETE} photos are required to complete a site survey ({photo_count} attached)",
        )
    if survey.surveyed_at is None:
        survey.surveyed_at = datetime.now(UTC).date()
    survey.surveyed_by_id = current_user.id
    survey.status = SiteSurveyStatus.COMPLETED
    survey.completed_at = datetime.now(UTC)

    write_audit_log_entry(
        db, current_user, "site_survey", survey.id, "status",
        old_value=SiteSurveyStatus.DRAFT.value, new_value=SiteSurveyStatus.COMPLETED.value,
        reason=f"{photo_count} photos attached",
    )

    db.commit()
    db.refresh(survey)
    return _to_out(db, survey)
