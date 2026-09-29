"""WP8 (correction plan, 2026-09-29): the in-app notification inbox API. Listing/read-status
is always scoped to current_user.id alone -- a notification's recipient IS the access control,
decided once at creation time in app/core/reminders.py."""
from datetime import UTC, date, datetime

from app.core.security import hash_password
from app.models.notification import Notification, NotificationEmailStatus, NotificationKind
from app.models.user import User, UserRole
from tests.test_quotations_admin import _director_headers, _login, _role_headers


def _notification(db_session, user_id, kind=NotificationKind.FOLLOW_UP_REMINDER, read_at=None, title="Test notification", **extra):
    row = Notification(
        user_id=user_id, kind=kind, notification_date=date.today(), title=title, body="Body text",
        read_at=read_at, **extra,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _pm_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.PM, "notif-pm@test.local")


def _sales_headers(client, db_session):
    return _role_headers(client, db_session, UserRole.SALES, "notif-sales@test.local")


def _pm_user_id(client, db_session):
    headers = _pm_headers(client, db_session)
    return client.get("/auth/me", headers=headers).json()["id"], headers


def test_user_sees_only_their_own_notifications(client, director_user, db_session):
    pm_id, pm_headers = _pm_user_id(client, db_session)
    _notification(db_session, pm_id, title="For the PM")
    _notification(db_session, director_user.id, title="For the Director")

    res = client.get("/notifications", headers=pm_headers)
    assert res.status_code == 200, res.text
    titles = [n["title"] for n in res.json()]
    assert titles == ["For the PM"]


def test_unread_count(client, director_user, db_session):
    pm_id, pm_headers = _pm_user_id(client, db_session)
    _notification(db_session, pm_id, title="Unread 1")
    _notification(db_session, pm_id, title="Unread 2")
    _notification(db_session, pm_id, title="Already read", read_at=datetime.now(UTC))

    res = client.get("/notifications/unread-count", headers=pm_headers)
    assert res.status_code == 200, res.text
    assert res.json()["unread"] == 2


def test_mark_read(client, director_user, db_session):
    pm_id, pm_headers = _pm_user_id(client, db_session)
    note = _notification(db_session, pm_id)

    res = client.post(f"/notifications/{note.id}/read", headers=pm_headers)
    assert res.status_code == 200, res.text
    assert res.json()["read_at"] is not None

    unread = client.get("/notifications/unread-count", headers=pm_headers).json()["unread"]
    assert unread == 0


def test_mark_read_on_someone_elses_notification_is_refused(client, director_user, db_session):
    pm_id, pm_headers = _pm_user_id(client, db_session)
    sales_headers = _sales_headers(client, db_session)
    note = _notification(db_session, pm_id)

    res = client.post(f"/notifications/{note.id}/read", headers=sales_headers)
    assert res.status_code == 404, res.text
    db_session.refresh(note)
    assert note.read_at is None


def test_mark_all_read(client, director_user, db_session):
    pm_id, pm_headers = _pm_user_id(client, db_session)
    _notification(db_session, pm_id, title="A")
    _notification(db_session, pm_id, title="B")
    _notification(db_session, director_user.id, title="Director's own")  # must be untouched

    res = client.post("/notifications/mark-all-read", headers=pm_headers)
    assert res.status_code == 200, res.text
    assert res.json()["unread"] == 0

    director_headers = _director_headers(client, director_user)
    director_unread = client.get("/notifications/unread-count", headers=director_headers).json()["unread"]
    assert director_unread == 1


def test_unread_only_filter(client, director_user, db_session):
    pm_id, pm_headers = _pm_user_id(client, db_session)
    _notification(db_session, pm_id, title="Unread")
    _notification(db_session, pm_id, title="Read", read_at=datetime.now(UTC))

    res = client.get("/notifications?unread_only=true", headers=pm_headers)
    titles = [n["title"] for n in res.json()]
    assert titles == ["Unread"]


# ---------------------------------------------------------------------------
# Delivery failures: Director/Admin only, and only past the retry cap
# ---------------------------------------------------------------------------


def test_delivery_failures_visible_to_director_only(client, director_user, db_session):
    from app.core.reminders import MAX_EMAIL_ATTEMPTS

    pm_id, _ = _pm_user_id(client, db_session)
    _notification(
        db_session, pm_id, title="Failed permanently",
        email_status=NotificationEmailStatus.FAILED, email_attempts=MAX_EMAIL_ATTEMPTS,
        email_last_error="SMTP timeout",
    )

    director_headers = _director_headers(client, director_user)
    res = client.get("/notifications/delivery-failures", headers=director_headers)
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1
    assert res.json()[0]["email_last_error"] == "SMTP timeout"

    sales_headers = _sales_headers(client, db_session)
    forbidden = client.get("/notifications/delivery-failures", headers=sales_headers)
    assert forbidden.status_code == 403, forbidden.text


def test_delivery_failures_excludes_in_progress_retries(client, director_user, db_session):
    pm_id, _ = _pm_user_id(client, db_session)
    _notification(
        db_session, pm_id, title="Still retrying",
        email_status=NotificationEmailStatus.FAILED, email_attempts=2,  # under the cap
    )

    director_headers = _director_headers(client, director_user)
    res = client.get("/notifications/delivery-failures", headers=director_headers)
    assert res.status_code == 200, res.text
    assert res.json() == []
