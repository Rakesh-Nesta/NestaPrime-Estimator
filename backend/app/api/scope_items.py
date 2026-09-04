import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import Project
from app.models.scope_item import ProjectScopeItem, ScopeItem, ScopeItemGroup

scope_items_router = APIRouter(prefix="/scope-items", tags=["scope-items"])
project_scope_items_router = APIRouter(prefix="/projects", tags=["project-scope-items"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("sales", "pm", "director")


class ScopeItemOut(BaseModel):
    id: uuid.UUID
    key: str
    display_order: int
    group: ScopeItemGroup
    name: str

    model_config = ConfigDict(from_attributes=True)


@scope_items_router.get("", response_model=list[ScopeItemOut])
def list_scope_items(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    return db.query(ScopeItem).order_by(ScopeItem.display_order).all()


class ProjectScopeItemCreate(BaseModel):
    scope_item_id: uuid.UUID
    note: str | None = None


class ProjectScopeItemOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    scope_item_id: uuid.UUID
    note: str | None

    model_config = ConfigDict(from_attributes=True)


@project_scope_items_router.post(
    "/{project_id}/scope-items", response_model=ProjectScopeItemOut, status_code=201
)
def add_project_scope_item(
    project_id: uuid.UUID,
    payload: ProjectScopeItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scope_item = db.query(ScopeItem).filter(ScopeItem.id == payload.scope_item_id).first()
    if not scope_item:
        raise HTTPException(status_code=404, detail="Scope item not found")

    existing = (
        db.query(ProjectScopeItem)
        .filter(
            ProjectScopeItem.project_id == project_id,
            ProjectScopeItem.scope_item_id == payload.scope_item_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Scope item already included on this project")

    row = ProjectScopeItem(project_id=project_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@project_scope_items_router.get(
    "/{project_id}/scope-items", response_model=list[ProjectScopeItemOut]
)
def list_project_scope_items(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return (
        db.query(ProjectScopeItem)
        .filter(ProjectScopeItem.project_id == project_id)
        .all()
    )


@project_scope_items_router.delete(
    "/{project_id}/scope-items/{selection_id}", status_code=204
)
def remove_project_scope_item(
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    row = (
        db.query(ProjectScopeItem)
        .filter(ProjectScopeItem.id == selection_id, ProjectScopeItem.project_id == project_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scope item selection not found")
    db.delete(row)
    db.commit()
