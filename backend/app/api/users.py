"""User management -- not part of the blueprint's own 19 ranked gaps (the
document's Part O data model names USERS/ROLES only as a table of the six
fixed roles, with no admin-UI spec at all), but a real operational gap: a
user account could otherwise only be created via a raw DB script
(scripts/seed_test_user.py). Director-only, deliberately small: create,
deactivate/reactivate, change role, reset password. Explicitly out of
scope for this pass (per direct instruction): editing a user's own
name/email, bulk import, a dedicated login-history view -- every write
here still goes through the existing audit log (document_type="user"),
so nothing is lost, just not given its own screen."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.audit_log import write_audit_log_entry
from app.core.auth import require_roles
from app.core.security import MIN_PASSWORD_LENGTH, hash_password, password_problem
from app.db.session import get_db
from app.models.user import User, UserRole

users_router = APIRouter(prefix="/users", tags=["users"])

# Amendment 59 (Section 62): who does what with people.
#   list     -- Admin, Director, PM (the create screen needs it to avoid duplicates)
#   create   -- Admin: any role; Director: any role except Admin; PM: Sales, Procurement, Site Engineer, CA/Tax
#   manage   -- (change role, deactivate, reset a password) Admin: anyone; Director: anyone except an Admin
# The route gates below admit the roles that may attempt an action; what each may do to WHOM is enforced in the
# handlers, server-side, with a plain reason.
LIST_ROLES = ("admin", "director", "pm")
CREATE_ROLES = ("admin", "director", "pm")
WRITE_ROLES = ("admin", "director")

PM_MAY_CREATE = frozenset(
    {UserRole.SALES, UserRole.PROCUREMENT, UserRole.SITE_ENGINEER, UserRole.CA_TAX}
)


def _active_admin_count(db: Session, exclude_id: uuid.UUID | None = None) -> int:
    query = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    return query.count()


def _require_may_create(db: Session, actor: User, role: UserRole) -> None:
    """403 with a plain reason when this actor may not create an account with this role."""
    if actor.role == UserRole.ADMIN:
        return
    if actor.role == UserRole.DIRECTOR:
        if role != UserRole.ADMIN:
            return
        # The one-time start: while no active Admin exists, the Director creates the first (and only then).
        if _active_admin_count(db) == 0:
            return
        raise HTTPException(status_code=403, detail="Only an Admin can create an Admin account")
    if actor.role == UserRole.PM and role in PM_MAY_CREATE:
        return
    raise HTTPException(
        status_code=403,
        detail="A PM can create Sales, Procurement, Site Engineer and CA/Tax accounts only",
    )


def _require_may_manage(db: Session, actor: User, target: User, new_role: UserRole | None = None) -> None:
    """403 when this actor may not change, deactivate or reset this person. A Director cannot touch an Admin, and
    cannot make anyone an Admin (except in the one-time start, while no active Admin exists)."""
    if actor.role == UserRole.ADMIN:
        return
    if target.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only an Admin can change an Admin account")
    if new_role == UserRole.ADMIN and _active_admin_count(db) > 0:
        raise HTTPException(status_code=403, detail="Only an Admin can make someone an Admin")


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@users_router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*LIST_ROLES)),
):
    return db.query(User).order_by(User.name).all()


class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    role: UserRole
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*CREATE_ROLES)),
):
    _require_may_create(db, current_user, payload.role)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    problem = password_problem(payload.password, payload.email)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    user = User(
        name=payload.name,
        email=payload.email,
        role=payload.role,
        hashed_password=hash_password(payload.password),
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    write_audit_log_entry(
        db, current_user, "user", user.id, "created",
        old_value=None, new_value=f"{payload.email} ({payload.role.value})", request=request,
    )
    db.commit()
    db.refresh(user)
    return user


def _active_director_count(db: Session, exclude_id: uuid.UUID) -> int:
    return (
        db.query(User)
        .filter(User.role == UserRole.DIRECTOR, User.is_active.is_(True), User.id != exclude_id)
        .count()
    )


class UserUpdate(BaseModel):
    """role and is_active only -- name/email edits are explicitly out of
    scope for this pass."""

    role: UserRole | None = None
    is_active: bool | None = None


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Two guardrails, enforced here server-side (not left to the
    frontend to withhold a button), both explicit product decisions
    rather than something the blueprint specifies:
    1. Can't deactivate your own account -- the classic admin-panel
       foot-gun (a Director locking themselves out, with no one left who
       can flip it back without a DB script).
    2. Can't demote or deactivate the last active Director -- otherwise
       the app could reach zero active Directors, and User Management
       itself is Director-only, so nobody could fix it without a DB
       script either. Checked generally against the active-Director
       count (covers a Director acting on themselves when they're the
       only one, or on the last *other* active Director), not just a
       self-check -- deactivation's own case is in practice only
       reachable via self (guardrail 1 already blocks that), but it's
       checked the same explicit way as the role-change case rather than
       relying on that reasoning holding forever."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _require_may_manage(db, current_user, user, new_role=payload.role)

    if payload.is_active is False and user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    if payload.is_active is False and user.role == UserRole.ADMIN:
        if _active_admin_count(db, exclude_id=user.id) == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate this user -- they are the last active Admin",
            )

    if payload.is_active is False and user.role == UserRole.DIRECTOR:
        if _active_director_count(db, exclude_id=user.id) == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate this user -- they are the last active Director",
            )

    if payload.role is not None and payload.role != user.role:
        if user.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
            if _active_admin_count(db, exclude_id=user.id) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot change this user's role -- they are the last active Admin",
                )
        if user.role == UserRole.DIRECTOR and payload.role != UserRole.DIRECTOR:
            if _active_director_count(db, exclude_id=user.id) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot change this user's role -- they are the last active Director",
                )
        # Amendment 59 item 9: nobody changes their own role either. Checked after the last-Director and
        # last-Admin guards so the sole Director or Admin still gets that more specific message.
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="You cannot change your own role")
        old_role = user.role
        user.role = payload.role
        write_audit_log_entry(
            db, current_user, "user", user.id, "role",
            old_value=old_role.value, new_value=payload.role.value, request=request,
        )

    if payload.is_active is not None and payload.is_active != user.is_active:
        old_active = user.is_active
        user.is_active = payload.is_active
        write_audit_log_entry(
            db, current_user, "user", user.id, "is_active",
            old_value=old_active, new_value=payload.is_active, request=request,
        )

    db.commit()
    db.refresh(user)
    return user


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


@users_router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    """Director sets a new password directly -- no email/reset-link flow,
    since this app has no mail provider wired up yet (M.7.4's real
    WhatsApp/email sending is itself still a deferred, correctly-absent
    piece). The audit entry records that a reset happened, never the
    password value itself, matching how no rate/setting change ever logs
    more than old/new -- here there simply is no safe "old" to log."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _require_may_manage(db, current_user, user)
    problem = password_problem(payload.new_password, user.email, user.hashed_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = True
    write_audit_log_entry(
        db, current_user, "user", user.id, "password",
        old_value="(reset)", new_value="(reset)", request=request,
    )
    db.commit()
    db.refresh(user)
    return user
