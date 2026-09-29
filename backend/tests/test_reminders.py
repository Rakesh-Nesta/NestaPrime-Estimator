"""WP8 (correction plan, 2026-09-29): the daily reminder/escalation run's core logic
(app/core/reminders.py), tested directly against run_daily_reminders rather than through the
cron script -- the script is a thin time-window + argument wrapper, this is where the actual
behaviour lives: who gets reminded, who gets escalated to, duplicate prevention, and retries."""
import uuid
from datetime import date, timedelta

import pytest

from app.core.reminders import (
    MAX_EMAIL_ATTEMPTS,
    FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT,
    preview_daily_reminders,
    run_daily_reminders,
)
from app.core.security import hash_password
from app.models.follow_up import FollowUp, FollowUpEntityType, FollowUpStatus
from app.models.notification import Notification, NotificationEmailStatus, NotificationKind
from app.models.setting import Setting, SettingScope
from app.models.user import User, UserRole
from tests.test_quotations_admin import _create_client_record, _create_project, _director_headers


def _pm_user(db_session, email="reminder-pm@test.local", name="Reminder PM"):
    user = User(name=name, email=email, hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _sales_user(db_session, email="reminder-sales@test.local", name="Reminder Sales", is_active=True, mail=True):
    user = User(
        name=name, email=email if mail else None, mobile=None if mail else "9876543210",
        hashed_password=hash_password("TestPass!1"), role=UserRole.SALES, is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _project_follow_up(db_session, project_id, owner_id, created_by_id, due_date, status=FollowUpStatus.OPEN):
    row = FollowUp(
        entity_type=FollowUpEntityType.PROJECT, entity_id=project_id, owner_id=owner_id,
        next_action="Follow up", due_date=due_date, status=status, created_by_id=created_by_id,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _project_for(client, headers, name):
    client_id = _create_client_record(client, headers, name)
    return _create_project(client, headers, client_id)


# ---------------------------------------------------------------------------
# Basic reminder creation
# ---------------------------------------------------------------------------


def test_reminder_created_for_an_accessible_overdue_follow_up(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Reminder Basic Client")
    fu = _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())

    assert result.owners_notified == 1
    assert result.reminder_notifications_created == 1
    note = db_session.query(Notification).filter(
        Notification.user_id == pm.id, Notification.follow_up_id == fu.id,
        Notification.kind == NotificationKind.FOLLOW_UP_REMINDER,
    ).first()
    assert note is not None
    assert "Overdue" in note.title
    assert note.entity_type == FollowUpEntityType.PROJECT
    assert str(note.entity_id) == project_id


def test_no_reminder_for_a_future_due_date(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Future Due Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() + timedelta(days=5))

    result = run_daily_reminders(db_session, date.today())
    assert result.reminder_notifications_created == 0


def test_no_reminder_for_a_completed_follow_up(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Completed Client")
    _project_follow_up(
        db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=3),
        status=FollowUpStatus.COMPLETED,
    )

    result = run_daily_reminders(db_session, date.today())
    assert result.reminder_notifications_created == 0


def test_no_reminder_for_an_unassigned_follow_up(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _project_for(client, headers, "Unassigned Client")
    _project_follow_up(db_session, project_id, None, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())
    assert result.reminder_notifications_created == 0
    assert result.owners_notified == 0


def test_inactive_owner_is_skipped_entirely(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    pm.is_active = False
    db_session.commit()
    project_id = _project_for(client, headers, "Inactive Owner Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())
    assert result.reminder_notifications_created == 0
    assert db_session.query(Notification).count() == 0


# ---------------------------------------------------------------------------
# Access-mismatch escalation (the confirmed WP5 gap) -- never emailed to the assignee
# ---------------------------------------------------------------------------


def test_access_mismatch_escalates_to_directors_and_never_reaches_the_assignee(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sales_owner = _pm_user(db_session, email="mismatch-owner@test.local", name="Mismatch Owner")
    sales_owner.role = UserRole.SALES
    db_session.commit()
    specialist = _sales_user(db_session, email="mismatch-specialist@test.local", name="Mismatch Specialist")

    switch = client.put("/ownership/switch", json={"on": True}, headers=director_headers)
    assert switch.status_code == 200, switch.text

    # Project owned by sales_owner; follow-up explicitly assigned to specialist (who doesn't
    # own the project) -- reproduces the confirmed WP5 access gap exactly.
    from tests.test_quotations_admin import _login

    sales_owner_headers = _login(client, sales_owner.email)
    client_id = _create_client_record(client, sales_owner_headers, "Mismatch Project Client")
    project_id = _create_project(client, sales_owner_headers, client_id)
    fu = _project_follow_up(db_session, project_id, specialist.id, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())

    assert result.access_mismatches_escalated == 1
    assert result.owners_notified == 0  # the specialist gets no digest -- nothing accessible to them

    to_specialist = db_session.query(Notification).filter(Notification.user_id == specialist.id).count()
    assert to_specialist == 0

    to_director = (
        db_session.query(Notification)
        .filter(Notification.user_id == director_user.id, Notification.kind == NotificationKind.ACCESS_MISMATCH_ESCALATION)
        .first()
    )
    assert to_director is not None
    assert "cannot open their own follow-up" in to_director.title
    assert "Mismatch Specialist" in to_director.body

    client.put("/ownership/switch", json={"on": False}, headers=director_headers)


def test_access_mismatch_reason_names_the_role_gap_not_the_ownership_switch_when_that_is_the_real_cause(
    client, director_user, db_session
):
    """A Cost Sheet's read_roles are sales/pm/director -- a Site Engineer assigned one has no
    read access at all, regardless of Amendment 60's own-records switch (which was never even
    turned on here). The escalation's explanation must name the actual cause (the role has no
    access to this record type) rather than pointing the Director at a switch that isn't why."""
    from app.models.document import CostSheet

    pm_owner = _pm_user(db_session, email="role-gap-owner@test.local", name="Role Gap Owner")
    specialist = User(
        name="Role Gap Specialist", email="role-gap-specialist@test.local",
        hashed_password=hash_password("TestPass!1"), role=UserRole.SITE_ENGINEER,
    )
    db_session.add(specialist)
    db_session.commit()

    from tests.test_quotations_admin import _login

    pm_owner_headers = _login(client, pm_owner.email)
    client_id = _create_client_record(client, pm_owner_headers, "Role Gap Client")
    project_id = _create_project(client, pm_owner_headers, client_id)

    cost_sheet = CostSheet(
        project_id=uuid.UUID(project_id), document_no="CS-ROLEGAP-0001", cost_total=1000,
        created_by_id=director_user.id,
    )
    db_session.add(cost_sheet)
    db_session.commit()

    fu = FollowUp(
        entity_type=FollowUpEntityType.COST_SHEET, entity_id=cost_sheet.id, owner_id=specialist.id,
        next_action="Follow up", due_date=date.today() - timedelta(days=1), status=FollowUpStatus.OPEN,
        created_by_id=director_user.id,
    )
    db_session.add(fu)
    db_session.commit()

    result = run_daily_reminders(db_session, date.today())
    assert result.access_mismatches_escalated == 1

    to_director = (
        db_session.query(Notification)
        .filter(Notification.user_id == director_user.id, Notification.kind == NotificationKind.ACCESS_MISMATCH_ESCALATION)
        .first()
    )
    assert to_director is not None
    assert "has no read access to this kind of record at all" in to_director.body
    assert "own-records setting" not in to_director.body


def test_no_access_mismatch_when_own_records_switch_is_off(client, director_user, db_session):
    """Same setup, switch OFF: the specialist CAN see it (per this session's own reconciled
    finding), so no escalation and a normal reminder instead."""
    director_headers = _director_headers(client, director_user)
    from tests.test_quotations_admin import _login

    sales_owner = _pm_user(db_session, email="noswitch-owner@test.local", name="No Switch Owner")
    sales_owner.role = UserRole.SALES
    db_session.commit()
    specialist = _sales_user(db_session, email="noswitch-specialist@test.local", name="No Switch Specialist")

    sales_owner_headers = _login(client, sales_owner.email)
    client_id = _create_client_record(client, sales_owner_headers, "No Switch Client")
    project_id = _create_project(client, sales_owner_headers, client_id)
    _project_follow_up(db_session, project_id, specialist.id, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())
    assert result.access_mismatches_escalated == 0
    assert result.owners_notified == 1


# ---------------------------------------------------------------------------
# Overdue-threshold escalation
# ---------------------------------------------------------------------------


def test_overdue_escalation_fires_at_default_threshold(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Threshold Client")
    _project_follow_up(
        db_session, project_id, pm.id, director_user.id,
        date.today() - timedelta(days=FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT),
    )

    result = run_daily_reminders(db_session, date.today())
    assert result.overdue_escalations_created == 1


def test_no_overdue_escalation_just_under_threshold(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Under Threshold Client")
    _project_follow_up(
        db_session, project_id, pm.id, director_user.id,
        date.today() - timedelta(days=FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT - 1),
    )

    result = run_daily_reminders(db_session, date.today())
    assert result.overdue_escalations_created == 0


def test_director_configured_threshold_is_respected(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    db_session.add(
        Setting(
            key="follow_up_overdue_escalation_days", scope=SettingScope.GLOBAL, value="1",
            effective_from=date(2020, 1, 1), changed_by_id=director_user.id,
        )
    )
    db_session.commit()
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Custom Threshold Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())
    assert result.overdue_escalations_created == 1


def test_director_receives_one_combined_digest_not_separate_emails(client, director_user, db_session, monkeypatch):
    """Both an access-mismatch escalation and an overdue-threshold escalation to the same
    Director on the same day must be ONE email, not two -- matching the same
    one-digest-per-recipient-per-day discipline as the assignee's own reminder."""
    from tests.test_quotations_admin import _login
    from app.core import reminders as reminders_module

    sent_calls = []
    monkeypatch.setattr(
        reminders_module.email_gateway, "send_email",
        lambda to, subject, body, **kw: sent_calls.append((to, subject)),
    )

    director_headers = _director_headers(client, director_user)
    sales_owner = _pm_user(db_session, email="digest-owner@test.local", name="Digest Owner")
    sales_owner.role = UserRole.SALES
    db_session.commit()
    specialist = _sales_user(db_session, email="digest-specialist@test.local", name="Digest Specialist")

    client.put("/ownership/switch", json={"on": True}, headers=director_headers)
    sales_owner_headers = _login(client, sales_owner.email)
    client_id = _create_client_record(client, sales_owner_headers, "Digest Client")
    project_id = _create_project(client, sales_owner_headers, client_id)
    # One mismatched (access-gap) follow-up and one plain overdue-threshold follow-up, both
    # ending up escalated to the same Director.
    _project_follow_up(db_session, project_id, specialist.id, director_user.id, date.today() - timedelta(days=1))
    pm = _pm_user(db_session, email="digest-pm@test.local", name="Digest PM")
    _project_follow_up(
        db_session, project_id, pm.id, director_user.id,
        date.today() - timedelta(days=FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT),
    )

    run_daily_reminders(db_session, date.today())

    director_emails = [c for c in sent_calls if c[0] == director_user.email]
    assert len(director_emails) == 1, sent_calls

    client.put("/ownership/switch", json={"on": False}, headers=director_headers)


# ---------------------------------------------------------------------------
# Idempotency and retries
# ---------------------------------------------------------------------------


def test_rerunning_the_same_day_creates_no_duplicate_notifications(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Idempotent Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    first = run_daily_reminders(db_session, date.today())
    second = run_daily_reminders(db_session, date.today())

    assert first.reminder_notifications_created == 1
    assert second.reminder_notifications_created == 0
    assert db_session.query(Notification).filter(Notification.kind == NotificationKind.FOLLOW_UP_REMINDER).count() == 1


def test_a_failed_email_retries_on_the_next_run_and_stops_at_the_cap(client, director_user, db_session, monkeypatch):
    from app.core import reminders as reminders_module
    from app.services.email_gateway import EmailGatewayError

    monkeypatch.setattr(
        reminders_module.email_gateway, "send_email",
        lambda *a, **kw: (_ for _ in ()).throw(EmailGatewayError("simulated failure")),
    )

    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Retry Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    for _ in range(MAX_EMAIL_ATTEMPTS + 2):
        run_daily_reminders(db_session, date.today())

    note = db_session.query(Notification).filter(Notification.kind == NotificationKind.FOLLOW_UP_REMINDER).first()
    assert note.email_status == NotificationEmailStatus.FAILED
    assert note.email_attempts == MAX_EMAIL_ATTEMPTS
    assert "simulated failure" in note.email_last_error


def test_a_successful_email_is_marked_sent_and_never_retried_again(client, director_user, db_session, monkeypatch):
    from app.core import reminders as reminders_module

    sent = []
    monkeypatch.setattr(
        reminders_module.email_gateway, "send_email",
        lambda to, subject, body, **kw: sent.append(to),
    )

    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session)
    project_id = _project_for(client, headers, "Success Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    run_daily_reminders(db_session, date.today())
    run_daily_reminders(db_session, date.today())

    assert len(sent) == 1  # not sent again on the second run
    note = db_session.query(Notification).filter(Notification.kind == NotificationKind.FOLLOW_UP_REMINDER).first()
    assert note.email_status == NotificationEmailStatus.SENT
    assert note.email_attempts == 1


def test_owner_with_no_email_still_gets_an_in_app_notification(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    mobile_only = _sales_user(db_session, email="unused@test.local", name="Mobile Only Owner", mail=False)
    project_id = _project_for(client, headers, "Mobile Only Client")
    _project_follow_up(db_session, project_id, mobile_only.id, director_user.id, date.today() - timedelta(days=1))

    result = run_daily_reminders(db_session, date.today())
    assert result.reminder_notifications_created == 1
    assert "Mobile Only Owner" in result.skipped_owners_no_email
    note = db_session.query(Notification).filter(Notification.user_id == mobile_only.id).first()
    assert note is not None
    assert note.email_status == NotificationEmailStatus.PENDING


# ---------------------------------------------------------------------------
# preview_daily_reminders -- the read-only pre-flight check (writes nothing, sends nothing)
# ---------------------------------------------------------------------------


def test_dry_run_preview_reports_an_accessible_reminder_without_writing_anything(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session, email="dryrun-owner@test.local", name="Dry Run Owner")
    project_id = _project_for(client, headers, "Dry Run Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    preview = preview_daily_reminders(db_session, date.today())

    assert db_session.query(Notification).count() == 0  # the whole point of a dry run
    assert preview.total_notifications == 1
    row = next(r for r in preview.recipients if r.name == "Dry Run Owner")
    assert row.reminder_count == 1
    assert row.email == "dryrun-owner@test.local"
    assert row.would_email is True
    assert row.exhausted_count == 0


def test_dry_run_preview_reports_access_mismatch_and_overdue_escalations_to_directors(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    sales_owner = _pm_user(db_session, email="dryrun-mismatch-owner@test.local", name="Dry Run Mismatch Owner")
    sales_owner.role = UserRole.SALES
    db_session.commit()
    specialist = _sales_user(db_session, email="dryrun-mismatch-specialist@test.local", name="Dry Run Specialist")

    switch = client.put("/ownership/switch", json={"on": True}, headers=headers)
    assert switch.status_code == 200, switch.text

    from tests.test_quotations_admin import _login

    sales_owner_headers = _login(client, sales_owner.email)
    client_id = _create_client_record(client, sales_owner_headers, "Dry Run Mismatch Client")
    project_id = _create_project(client, sales_owner_headers, client_id)
    _project_follow_up(db_session, project_id, specialist.id, director_user.id, date.today() - timedelta(days=5))

    preview = preview_daily_reminders(db_session, date.today())

    assert db_session.query(Notification).count() == 0
    director_row = next(r for r in preview.recipients if r.name == director_user.name)
    assert director_row.access_mismatch_count == 1
    assert director_row.overdue_escalation_count == 1  # 5 days overdue, past the default 3-day threshold
    assert not any(r.name == "Dry Run Specialist" for r in preview.recipients)  # never previewed as a recipient

    client.put("/ownership/switch", json={"on": False}, headers=headers)


def test_dry_run_preview_shows_a_failed_send_as_still_retryable_not_zero(client, director_user, db_session, monkeypatch):
    """The point of reusing the retry rule: an item that already exists but failed to send (and
    is still under the cap) is NOT "nothing new" -- a real run would retry it, so the preview
    must still count it, exactly the way it would understate reality if it only checked
    existence."""
    from app.core import reminders as reminders_module
    from app.services.email_gateway import EmailGatewayError

    monkeypatch.setattr(
        reminders_module.email_gateway, "send_email",
        lambda *a, **kw: (_ for _ in ()).throw(EmailGatewayError("simulated failure")),
    )

    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session, email="dryrun-retry@test.local", name="Dry Run Retry Owner")
    project_id = _project_for(client, headers, "Dry Run Retry Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    run_daily_reminders(db_session, date.today())  # real run, send fails, attempts=1 (< cap)

    preview = preview_daily_reminders(db_session, date.today())
    row = next(r for r in preview.recipients if r.name == "Dry Run Retry Owner")
    assert row.reminder_count == 1  # still due to be retried, correctly NOT reported as zero
    assert row.exhausted_count == 0


def test_dry_run_preview_shows_zero_once_actually_sent(client, director_user, db_session, monkeypatch):
    from app.core import reminders as reminders_module

    monkeypatch.setattr(reminders_module.email_gateway, "send_email", lambda *a, **kw: None)

    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session, email="dryrun-sent@test.local", name="Dry Run Sent Owner")
    project_id = _project_for(client, headers, "Dry Run Sent Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    run_daily_reminders(db_session, date.today())  # real run, send succeeds

    preview = preview_daily_reminders(db_session, date.today())
    assert not any(r.name == "Dry Run Sent Owner" for r in preview.recipients)  # nothing left to do


def test_dry_run_preview_reports_exhausted_items_separately_and_stops_counting_them_as_pending(
    client, director_user, db_session, monkeypatch
):
    from app.core import reminders as reminders_module
    from app.services.email_gateway import EmailGatewayError

    monkeypatch.setattr(
        reminders_module.email_gateway, "send_email",
        lambda *a, **kw: (_ for _ in ()).throw(EmailGatewayError("simulated failure")),
    )

    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session, email="dryrun-exhausted@test.local", name="Dry Run Exhausted Owner")
    project_id = _project_for(client, headers, "Dry Run Exhausted Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    for _ in range(MAX_EMAIL_ATTEMPTS):
        run_daily_reminders(db_session, date.today())  # exhausts the retry cap for real

    preview = preview_daily_reminders(db_session, date.today())
    row = next(r for r in preview.recipients if r.name == "Dry Run Exhausted Owner")
    assert row.exhausted_count == 1
    assert row.reminder_count == 0  # will NOT be retried this run -- must not be counted as pending
    assert row.total == 0  # exhausted items are a separate bucket, not part of "would be emailed"


def test_dry_run_preview_empty_when_nothing_is_due(client, director_user, db_session):
    preview = preview_daily_reminders(db_session, date.today())
    assert preview.recipients == []
    assert preview.total_notifications == 0


def test_dry_run_preview_makes_no_database_changes_at_all(client, director_user, db_session, monkeypatch):
    """Not just "no new rows" -- an existing row's read status, email status and retry counter
    must all come out byte-for-byte identical, since preview_daily_reminders must never touch a
    row it looks at, only read it."""
    from app.core import reminders as reminders_module
    from app.services.email_gateway import EmailGatewayError

    monkeypatch.setattr(
        reminders_module.email_gateway, "send_email",
        lambda *a, **kw: (_ for _ in ()).throw(EmailGatewayError("simulated failure")),
    )

    headers = _director_headers(client, director_user)
    pm = _pm_user(db_session, email="dryrun-untouched@test.local", name="Dry Run Untouched Owner")
    project_id = _project_for(client, headers, "Dry Run Untouched Client")
    _project_follow_up(db_session, project_id, pm.id, director_user.id, date.today() - timedelta(days=1))

    run_daily_reminders(db_session, date.today())  # creates one real, FAILED, attempts=1 row
    before = db_session.query(Notification).order_by(Notification.id).all()
    snapshot = [
        (n.id, n.read_at, n.email_status, n.email_attempts, n.email_last_error, n.email_sent_at) for n in before
    ]
    assert len(snapshot) == 1

    preview_daily_reminders(db_session, date.today())

    after = db_session.query(Notification).order_by(Notification.id).all()
    after_snapshot = [
        (n.id, n.read_at, n.email_status, n.email_attempts, n.email_last_error, n.email_sent_at) for n in after
    ]
    assert after_snapshot == snapshot
    assert len(after) == 1  # no new row either
