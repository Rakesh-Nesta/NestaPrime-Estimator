import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.documents import _derived_client_status, _effective_estimate_status
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.document import Estimate, EstimateOption, EstimateStatus
from app.models.project import Project

estimates_admin_router = APIRouter(tags=["estimates-admin"])

# Amendment 12 (Section 11): the Dashboard's "Pending Estimates" tile had no
# screen behind it -- only the count. Same broad visibility as the
# Dashboard summary itself (dashboard.py) rather than Director-only, since
# an Estimate carries client-facing price ranges, not cost/margin --
# different footing from Quotations Admin's stricter gate.
ROLES = ("sales", "pm", "director", "procurement", "site_engineer", "ca_tax")


class EstimateSummaryOut(BaseModel):
    id: uuid.UUID
    document_no: str
    status: EstimateStatus
    client_status: str
    project_id: uuid.UUID
    project_no: str
    client_name: str
    created_at: datetime
    sent_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


def _to_summary(db: Session, estimate: Estimate, project: Project, client_name: str) -> EstimateSummaryOut:
    options = db.query(EstimateOption).filter(EstimateOption.estimate_id == estimate.id).all()
    return EstimateSummaryOut(
        id=estimate.id,
        document_no=estimate.document_no,
        status=_effective_estimate_status(estimate),
        client_status=_derived_client_status(options),
        project_id=project.id,
        project_no=project.project_no,
        client_name=client_name,
        created_at=estimate.created_at,
        sent_at=estimate.sent_at,
    )


@estimates_admin_router.get("/estimates", response_model=list[EstimateSummaryOut])
def list_all_estimates(
    search: str | None = None,
    status: EstimateStatus | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    query = (
        db.query(Estimate, Project, Client.name)
        .join(Project, Estimate.project_id == Project.id)
        .join(Client, Project.client_id == Client.id)
    )
    if search:
        needle = f"%{search}%"
        query = query.filter((Project.project_no.ilike(needle)) | (Client.name.ilike(needle)))

    rows = query.order_by(Estimate.created_at.desc()).all()
    out = []
    for estimate, project, client_name in rows:
        summary = _to_summary(db, estimate, project, client_name)
        if status is not None and summary.status != status:
            continue
        out.append(summary)
    return out
