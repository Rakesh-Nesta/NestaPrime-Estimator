import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.project import Project
from app.models.scope_item import ProjectScopeItem, ScopeItem, ScopeItemGroup

scope_items_router = APIRouter(prefix="/scope-items", tags=["scope-items"])
project_scope_items_router = APIRouter(prefix="/projects", tags=["project-scope-items"])

READ_ROLES = ("sales", "pm", "director", "procurement", "site_engineer")
WRITE_ROLES = ("sales", "pm", "director")
# Q.2 rule 6: "Master Settings screen is Director-only (PM read-only)."
MASTER_WRITE_ROLES = ("director",)


class ScopeItemOut(BaseModel):
    id: uuid.UUID
    key: str
    display_order: int
    group: ScopeItemGroup
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@scope_items_router.get("", response_model=list[ScopeItemOut])
def list_scope_items(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*READ_ROLES)),
):
    query = db.query(ScopeItem)
    if not include_inactive:
        query = query.filter(ScopeItem.is_active.is_(True))
    return query.order_by(ScopeItem.display_order).all()


class ScopeItemCreate(BaseModel):
    key: str
    display_order: int
    group: ScopeItemGroup
    name: str


class ScopeItemUpdate(BaseModel):
    """key is deliberately not editable -- nothing elsewhere currently
    matches on a scope item's key, but keeping the same immutable-key
    convention as Sport avoids introducing a silent-breakage risk later."""

    display_order: int | None = None
    group: ScopeItemGroup | None = None
    name: str | None = None
    is_active: bool | None = None


@scope_items_router.post("", response_model=ScopeItemOut, status_code=201)
def create_scope_item(
    payload: ScopeItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    if db.query(ScopeItem).filter(ScopeItem.key == payload.key).first():
        raise HTTPException(status_code=409, detail=f"A scope item with key '{payload.key}' already exists")
    scope_item = ScopeItem(**payload.model_dump())
    db.add(scope_item)
    db.commit()
    db.refresh(scope_item)
    return scope_item


@scope_items_router.patch("/{scope_item_id}", response_model=ScopeItemOut)
def update_scope_item(
    scope_item_id: uuid.UUID,
    payload: ScopeItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*MASTER_WRITE_ROLES)),
):
    scope_item = db.query(ScopeItem).filter(ScopeItem.id == scope_item_id).first()
    if not scope_item:
        raise HTTPException(status_code=404, detail="Scope item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scope_item, field, value)
    db.commit()
    db.refresh(scope_item)
    return scope_item


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


class ProjectOut(BaseModel):
    id: uuid.UUID
    scope_confirmed_empty_at: datetime | None
    scope_confirmed_empty_by_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


@project_scope_items_router.post(
    "/{project_id}/scope-items/confirm-empty", response_model=ProjectOut
)
def confirm_empty_scope(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """WP7 (correction plan, 2026-09-28): the explicit "confirmed zero additional scope"
    action the Scope readiness check (app/core/readiness.py) accepts as an alternative to
    at least one ProjectScopeItem existing -- see Project.scope_confirmed_empty_at's own
    docstring for why this is needed (a project nobody has looked at and one genuinely
    scoped as empty both show zero rows otherwise). Idempotent: repeating it just refreshes
    who/when, same as re-confirming is meant to work."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.scope_confirmed_empty_at = datetime.now(UTC)
    project.scope_confirmed_empty_by_id = current_user.id

    write_audit_log_entry(
        db, current_user, "project", project.id, "scope_confirmed_empty_at",
        old_value=None, new_value=project.scope_confirmed_empty_at.isoformat(), request=request,
    )

    db.commit()
    db.refresh(project)
    return project
