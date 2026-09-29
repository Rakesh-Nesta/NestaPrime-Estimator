"""WP8 (correction plan, 2026-09-29): the daily 9:00 Asia/Kolkata follow-up reminder +
escalation run. Called by backend/scripts/send_daily_follow_up_reminders.py (a cron-invoked
script, matching this codebase's only existing recurring-job precedent, deploy/backup_db.sh's
OS crontab entry -- there is no in-process scheduler anywhere in this app).

Idempotent and retry-safe by construction, not by convention: every Notification this run
would create is looked up first (unique on user_id+follow_up_id+kind+notification_date,
enforced by a DB index -- see app/models/notification.py), so invoking this function twice for
the same IST calendar date, or invoking it after a previous run partially failed, never
double-creates a notification and never double-sends an email that already succeeded. This is
what makes "retries" (an explicit WP8 requirement) safe without a queue: the cron entry can
simply invoke the script every N minutes inside the 9:00-9:30 IST window, and a later tick
picks up only what an earlier tick didn't finish.

Three distinct outcomes per due/overdue FollowUp, decided fresh each run:
1. The owner can access it (check_follow_up_access passes) -> one FOLLOW_UP_REMINDER
   notification, batched into that owner's own daily digest email.
2. The owner CANNOT access it -- the confirmed WP5 gap (app/core/follow_up_entities.py's own
   docstring: Amendment 60 own-records scoping only ever checks the PARENT record's owner,
   never the follow-up row's own explicit assignee) -- never emailed to the owner (that would
   be exactly the "unusable link" WP8 was explicitly told not to send); instead escalated to
   every active Director as an ACCESS_MISMATCH_ESCALATION, batched into a separate Director
   digest.
3. Independently of (1)/(2): a FollowUp overdue at least the Director-configurable threshold
   (Setting key FOLLOW_UP_OVERDUE_ESCALATION_DAYS_KEY) additionally raises a
   FOLLOW_UP_OVERDUE_ESCALATION to every active Director, in the same Director digest.

No AuditLogEntry is written for any of this -- write_audit_log_entry requires a real logged-in
current_user (its user_id column is NOT NULL, with no existing precedent anywhere in this
codebase for a non-human actor); Notification IS the honest record of what was communicated,
to whom, and with what delivery outcome, which is more specific than a generic audit entry
would be anyway."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.settings import get_current_setting_value
from app.core import follow_up_entities
from app.core.settings_parse import parse_setting_number
from app.models.client import Client
from app.models.document import CostSheet, Estimate, Quotation
from app.models.follow_up import TERMINAL_FOLLOW_UP_STATUSES, FollowUp, FollowUpEntityType
from app.models.notification import Notification, NotificationEmailStatus, NotificationKind
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.user import User, UserRole
from app.services import email_gateway

FOLLOW_UP_OVERDUE_ESCALATION_DAYS_KEY = "follow_up_overdue_escalation_days"
FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT = 3

# After this many failed attempts an email is left FAILED permanently for this notification --
# still visible in-app and in the delivery-failures view, just no longer retried forever.
MAX_EMAIL_ATTEMPTS = 5


@dataclass
class ReminderRunResult:
    owners_notified: int = 0
    reminder_notifications_created: int = 0
    access_mismatches_escalated: int = 0
    overdue_escalations_created: int = 0
    digest_emails_sent: int = 0
    digest_emails_failed: int = 0
    skipped_owners_no_email: list[str] = field(default_factory=list)


def _escalation_threshold_days(db: Session) -> int:
    raw = get_current_setting_value(db, FOLLOW_UP_OVERDUE_ESCALATION_DAYS_KEY)
    if raw is None:
        return FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT
    try:
        return parse_setting_number(FOLLOW_UP_OVERDUE_ESCALATION_DAYS_KEY, raw, int)
    except HTTPException:
        # A malformed setting value must never crash the whole daily run -- fall back and
        # let whoever broke the setting fix it at their own pace, same "never 500 on bad
        # config" discipline documents.py's own SLA/validity-day settings already follow.
        return FOLLOW_UP_OVERDUE_ESCALATION_DAYS_DEFAULT


def resolve_entity_label(db: Session, entity_type: FollowUpEntityType, entity_id: uuid.UUID) -> str:
    """A short, human display label for a FollowUp's parent record -- used in notification
    titles/bodies. Never includes cost/margin figures (K.3) -- only names/numbers a reminder
    recipient could already see on that record's own screen, and only for the entity types a
    FollowUp is actually created on in practice today (Project/Opportunity/Client cover the
    overwhelming majority); anything else gets an honest generic fallback rather than a
    fabricated-looking label."""
    if entity_type == FollowUpEntityType.PROJECT:
        row = db.query(Project).filter(Project.id == entity_id).first()
        return f"Project {row.project_no}" if row else "a Project"
    if entity_type == FollowUpEntityType.OPPORTUNITY:
        row = db.query(Opportunity).filter(Opportunity.id == entity_id).first()
        return f"Opportunity: {row.lead_name}" if row else "an Opportunity"
    if entity_type == FollowUpEntityType.CLIENT:
        row = db.query(Client).filter(Client.id == entity_id).first()
        return f"Client: {row.name}" if row else "a Client"
    if entity_type == FollowUpEntityType.COST_SHEET:
        row = db.query(CostSheet).filter(CostSheet.id == entity_id).first()
        return f"Cost Sheet {row.document_no}" if row else "a Cost Sheet"
    if entity_type == FollowUpEntityType.ESTIMATE:
        row = db.query(Estimate).filter(Estimate.id == entity_id).first()
        return f"Estimate {row.document_no}" if row else "an Estimate"
    if entity_type == FollowUpEntityType.QUOTATION:
        row = db.query(Quotation).filter(Quotation.id == entity_id).first()
        return f"Quotation {row.document_no}" if row else "a Quotation"
    return entity_type.value.replace("_", " ").title()


def _get_or_create_notification(
    db: Session, *, user_id: uuid.UUID, follow_up_id: uuid.UUID, kind: NotificationKind,
    notification_date: date, title: str, body: str, entity_type: FollowUpEntityType, entity_id: uuid.UUID,
) -> tuple[Notification, bool]:
    """Idempotent insert-or-get. Uses a SAVEPOINT (begin_nested), not the outer transaction,
    so a race on one row (two overlapping cron ticks) never discards every other notification
    already staged in this same run for other owners/directors."""
    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id, Notification.follow_up_id == follow_up_id,
            Notification.kind == kind, Notification.notification_date == notification_date,
        )
        .first()
    )
    if existing is not None:
        return existing, False
    row = Notification(
        user_id=user_id, follow_up_id=follow_up_id, kind=kind, notification_date=notification_date,
        title=title, body=body, entity_type=entity_type, entity_id=entity_id,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
        return row, True
    except IntegrityError:
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id, Notification.follow_up_id == follow_up_id,
                Notification.kind == kind, Notification.notification_date == notification_date,
            )
            .first()
        )
        return existing, False


def _send_digest(db: Session, recipient: User, notifications: list[Notification], subject: str, intro: str) -> bool | None:
    """Sends ONE email covering every not-yet-successfully-sent notification in the list
    (newly created this run, or FAILED with attempts remaining from an earlier run today).
    Returns True (sent), False (failed), or None (nothing needed sending -- no failure, just
    nothing to report). Every row in the batch gets the same outcome recorded, since they were
    genuinely sent (or not) together in the one email."""
    to_send = [
        n for n in notifications
        if n.email_status != NotificationEmailStatus.SENT and n.email_attempts < MAX_EMAIL_ATTEMPTS
    ]
    if not to_send:
        return None
    if not recipient.email:
        return None  # no mailbox to send to -- the in-app notifications still stand on their own
    body = intro + "\n\n" + "\n\n".join(f"- {n.title}\n  {n.body}" for n in to_send)
    for n in to_send:
        n.email_attempts += 1
    try:
        email_gateway.send_email(to=recipient.email, subject=subject, body=body)
    except email_gateway.EmailGatewayError as exc:
        for n in to_send:
            n.email_status = NotificationEmailStatus.FAILED
            n.email_last_error = str(exc)[:500]
        return False
    for n in to_send:
        n.email_status = NotificationEmailStatus.SENT
        n.email_sent_at = datetime.now(UTC)
        n.email_last_error = None
    return True


def run_daily_reminders(db: Session, today_ist: date) -> ReminderRunResult:
    result = ReminderRunResult()

    due_or_overdue = (
        db.query(FollowUp)
        .filter(FollowUp.status.notin_(TERMINAL_FOLLOW_UP_STATUSES))
        .filter(FollowUp.due_date <= today_ist)
        .filter(FollowUp.owner_id.isnot(None))
        .all()
    )

    by_owner: dict[uuid.UUID, list[FollowUp]] = defaultdict(list)
    for fu in due_or_overdue:
        by_owner[fu.owner_id].append(fu)

    director_escalation_notifications: dict[uuid.UUID, list[Notification]] = defaultdict(list)
    active_directors = db.query(User).filter(User.role == UserRole.DIRECTOR, User.is_active.is_(True)).all()

    for owner_id, follow_ups in by_owner.items():
        owner = db.query(User).filter(User.id == owner_id).first()
        if owner is None or not owner.is_active:
            continue  # no live account to notify

        accessible, mismatched = [], []
        for fu in follow_ups:
            try:
                follow_up_entities.check_follow_up_access(db, owner, fu.entity_type, fu.entity_id, need="read")
                accessible.append(fu)
            except HTTPException as exc:
                # check_follow_up_access's own two raises distinguish the cause cleanly: a 403
                # means the role itself has no read access to this kind of record at all (no
                # setting to check); a 404 is the own-records-scoping 404 it deliberately raises
                # in place of a 403 (see its own docstring) -- Amendment 60's own-records setting
                # really is the thing to check there.
                mismatched.append((fu, exc.status_code))

        owner_notifications = []
        for fu in accessible:
            overdue = fu.due_date < today_ist
            label = resolve_entity_label(db, fu.entity_type, fu.entity_id)
            row, created = _get_or_create_notification(
                db, user_id=owner.id, follow_up_id=fu.id, kind=NotificationKind.FOLLOW_UP_REMINDER,
                notification_date=today_ist,
                title=f"{'Overdue' if overdue else 'Due today'}: {fu.next_action}",
                body=f"{label} -- due {fu.due_date.isoformat()}",
                entity_type=fu.entity_type, entity_id=fu.entity_id,
            )
            owner_notifications.append(row)
            if created:
                result.reminder_notifications_created += 1

        for fu, status_code in mismatched:
            label = resolve_entity_label(db, fu.entity_type, fu.entity_id)
            contact = owner.email or owner.mobile or "no contact on file"
            reason = (
                "Amendment 60's own-records setting restricting it to the record's owner"
                if status_code == 404
                else f"{owner.role.value}'s role has no read access to this kind of record at all"
            )
            for director in active_directors:
                row, created = _get_or_create_notification(
                    db, user_id=director.id, follow_up_id=fu.id, kind=NotificationKind.ACCESS_MISMATCH_ESCALATION,
                    notification_date=today_ist,
                    title=f"Access mismatch: {owner.name} cannot open their own follow-up",
                    body=(
                        f"{owner.name} ({contact}) is assigned \"{fu.next_action}\" on {label}, due "
                        f"{fu.due_date.isoformat()}, but does not currently have access to open it "
                        f"(likely {reason}). Not emailed to them -- review the assignment or ownership "
                        f"directly."
                    ),
                    entity_type=fu.entity_type, entity_id=fu.entity_id,
                )
                director_escalation_notifications[director.id].append(row)
                if created:
                    result.access_mismatches_escalated += 1

        if owner_notifications:
            result.owners_notified += 1
            outcome = _send_digest(
                db, owner, owner_notifications,
                subject=f"NestaPrime: {len(owner_notifications)} follow-up(s) due or overdue",
                intro="Follow-ups needing your attention today:",
            )
            if outcome is True:
                result.digest_emails_sent += 1
            elif outcome is False:
                result.digest_emails_failed += 1
            elif not owner.email:
                result.skipped_owners_no_email.append(owner.name)

    threshold_days = _escalation_threshold_days(db)
    for fu in due_or_overdue:
        if (today_ist - fu.due_date).days < threshold_days:
            continue
        label = resolve_entity_label(db, fu.entity_type, fu.entity_id)
        for director in active_directors:
            row, created = _get_or_create_notification(
                db, user_id=director.id, follow_up_id=fu.id, kind=NotificationKind.FOLLOW_UP_OVERDUE_ESCALATION,
                notification_date=today_ist,
                title=f"Overdue {(today_ist - fu.due_date).days}d: {fu.next_action}",
                body=f"{label} -- due {fu.due_date.isoformat()}, past the {threshold_days}-day escalation threshold",
                entity_type=fu.entity_type, entity_id=fu.entity_id,
            )
            director_escalation_notifications[director.id].append(row)
            if created:
                result.overdue_escalations_created += 1

    for director_id, notifications in director_escalation_notifications.items():
        director = next((d for d in active_directors if d.id == director_id), None)
        if director is None:
            continue
        outcome = _send_digest(
            db, director, notifications,
            subject=f"NestaPrime: {len(notifications)} follow-up escalation(s)",
            intro="Follow-ups escalated for your attention today:",
        )
        if outcome is True:
            result.digest_emails_sent += 1
        elif outcome is False:
            result.digest_emails_failed += 1

    db.commit()
    return result
