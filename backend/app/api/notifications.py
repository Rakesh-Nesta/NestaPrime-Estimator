"""WP8 (correction plan, 2026-09-29): the in-app notification inbox. A notification is
always addressed to exactly one User (Notification.user_id) -- listing/marking-read is
therefore always scoped to `current_user.id` alone, no broader entity-level permission check
is needed here (unlike Project Overview's aggregation, this endpoint was never going to show
anyone a record they couldn't already reach -- it only ever shows what was already decided,
at creation time in app/core/reminders.py, to belong to this exact person)."""
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.notification import Notification, NotificationEmailStatus, NotificationKind
from app.models.user import User

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])

# A visible-delivery-failures view is inherently about every recipient's mail, not just the
# viewer's own -- Director/Admin only, matching who already manages people/access/technical
# settings elsewhere in this app (Amendment 59's own ADMIN role docstring).
DELIVERY_FAILURES_ROLES = ("director", "admin")


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    notification_date: date
    title: str
    body: str
    follow_up_id: uuid.UUID | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    read_at: datetime | None
    email_status: NotificationEmailStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnreadCountOut(BaseModel):
    unread: int


@notifications_router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.order_by(Notification.created_at.desc()).limit(min(limit, 200)).all()


@notifications_router.get("/unread-count", response_model=UnreadCountOut)
def get_unread_count(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .count()
    )
    return UnreadCountOut(unread=count)


@notifications_router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return row


@notifications_router.post("/mark-all-read", response_model=UnreadCountOut)
def mark_all_read(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    now = datetime.now(UTC)
    (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .update({"read_at": now}, synchronize_session=False)
    )
    db.commit()
    return UnreadCountOut(unread=0)


class DeliveryFailureOut(BaseModel):
    id: uuid.UUID
    recipient_id: uuid.UUID
    recipient_name: str
    kind: NotificationKind
    notification_date: date
    title: str
    email_attempts: int
    email_last_error: str | None

    model_config = ConfigDict(from_attributes=True)


@notifications_router.get("/delivery-failures", response_model=list[DeliveryFailureOut])
def list_delivery_failures(
    db: Session = Depends(get_db), current_user=Depends(require_roles(*DELIVERY_FAILURES_ROLES))
):
    """Every notification whose email has been retried to the cap (app/core/reminders.py's
    MAX_EMAIL_ATTEMPTS) and still hasn't sent -- the visible-failure half of WP8's own
    duplicate-prevention/retries/visible-failures requirement. Anything still under the
    attempt cap is a normal, expected in-progress retry, not a failure to surface here."""
    from app.core.reminders import MAX_EMAIL_ATTEMPTS

    rows = (
        db.query(Notification, User)
        .join(User, Notification.user_id == User.id)
        .filter(Notification.email_status == NotificationEmailStatus.FAILED)
        .filter(Notification.email_attempts >= MAX_EMAIL_ATTEMPTS)
        .order_by(Notification.notification_date.desc())
        .all()
    )
    return [
        DeliveryFailureOut(
            id=n.id, recipient_id=u.id, recipient_name=u.name, kind=n.kind,
            notification_date=n.notification_date, title=n.title,
            email_attempts=n.email_attempts, email_last_error=n.email_last_error,
        )
        for n, u in rows
    ]
