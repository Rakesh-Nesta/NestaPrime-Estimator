"""Amendment 59 (Section 62): the small "system facts" Overview an Admin sees instead of the business dashboard.

An Admin has no business records, so the dashboard's counts and revenue are not theirs. This shows people and
recent activity only -- who exists, who is locked or still on a temporary password, and the latest audit entries
(with cost and margin values hidden for an Admin, in full for the Director)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.audit_log import AuditLogEntryOut, mask_for_role
from app.core.auth import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLogEntry
from app.models.user import User, UserRole

admin_overview_router = APIRouter(prefix="/admin", tags=["admin"])

RECENT_ACTIVITY_LIMIT = 15


class AdminOverviewOut(BaseModel):
    active_users_by_role: dict[str, int]
    inactive_users: int
    locked_accounts: int
    awaiting_password_change: int
    recent_activity: list[AuditLogEntryOut]


@admin_overview_router.get("/overview", response_model=AdminOverviewOut)
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "director")),
):
    now = datetime.now(UTC).replace(tzinfo=None)
    users = db.query(User).all()
    by_role = {role.value: 0 for role in UserRole}
    for user in users:
        if user.is_active:
            by_role[user.role.value] += 1
    entries = db.query(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc()).limit(RECENT_ACTIVITY_LIMIT).all()
    return AdminOverviewOut(
        active_users_by_role=by_role,
        inactive_users=sum(1 for u in users if not u.is_active),
        locked_accounts=sum(1 for u in users if u.locked_until is not None and u.locked_until > now),
        awaiting_password_change=sum(1 for u in users if u.is_active and u.must_change_password),
        recent_activity=[
            mask_for_role(AuditLogEntryOut.model_validate(entry), current_user.role.value) for entry in entries
        ],
    )
