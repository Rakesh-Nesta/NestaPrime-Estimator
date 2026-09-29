"""WP8 (correction plan, 2026-09-29): the daily 9:00 Asia/Kolkata follow-up reminder run.
Invoked by an OS-level crontab entry (this app has no in-process scheduler -- see
deploy/backup_db.sh for the only other existing recurring-job precedent, an OS crontab
calling a standalone script directly).

Deliberately invoked more often than once a day (recommended: every 15 minutes) rather than
relying on the server's own OS timezone matching Asia/Kolkata exactly -- this script computes
the current Asia/Kolkata time itself (via zoneinfo, no assumption about the server's own TZ)
and only does real work inside the 09:00-09:30 IST window each day, using
app.core.reminders.run_daily_reminders's own per-notification idempotency (unique on
recipient+follow-up+kind+date) to make repeated invocations inside that window safe: an
earlier tick's successes are never re-sent, and anything that failed or is newly due gets
picked up by a later tick -- this IS the "retries" mechanism, no queue needed.

--force bypasses the time-window check (for a manual/ops re-run) but never bypasses the
per-notification idempotency itself -- it cannot cause a duplicate send for something already
successfully delivered today. It also does NOT scope the run to one recipient: it processes
every eligible follow-up and owner in the system, exactly like the real 9am run, so it sends
real reminder and escalation emails to everyone currently eligible. It is a real activation,
not a test.

--dry-run is the actual read-only check: reports who WOULD be notified, how many reminder/
escalation items each, and anything already sitting exhausted in the delivery-failures view,
without creating any Notification row, changing any existing row (read status, retry counters,
email status), or sending any email (see app.core.reminders.preview_daily_reminders -- it
reuses the real run's own selection, access, deduplication and retry-cap logic exactly, so it
cannot drift from what a real run would do). Ignores the time window. Use this -- never --force
-- to review who a run would reach before installing the cron or before a manual --force run.

--dry-run, --force and the real scheduled run are three different things, deliberately kept
distinct here:
  - --dry-run:            preview only, safe to run any number of times, changes nothing.
  - --force:               a REAL run, right now, for everyone currently eligible -- identical
                            in effect to the scheduled run, just not waiting for the window.
  - the scheduled run:     the same real run, firing automatically inside 09:00-09:30 IST.
A --dry-run's picture reflects the moment it was run, using today's calendar date -- due dates,
ownership, and the overdue-escalation-threshold setting can all change before an actual run
(scheduled or --force) fires, so treat it as a snapshot, not a guarantee, and re-run it
immediately before relying on it for a same-day decision.
"""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.reminders import preview_daily_reminders, run_daily_reminders
from app.db.session import SessionLocal

IST = ZoneInfo("Asia/Kolkata")
WINDOW_START_MINUTES = 9 * 60  # 09:00
WINDOW_END_MINUTES = 9 * 60 + 30  # 09:30


def _in_window(now_ist: datetime) -> bool:
    minutes = now_ist.hour * 60 + now_ist.minute
    return WINDOW_START_MINUTES <= minutes < WINDOW_END_MINUTES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Run now regardless of the 09:00-09:30 IST window. Sends real emails to everyone currently eligible -- not a test.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read-only preview: who would be notified, how many items each, and anything "
             "already exhausted -- writes and sends nothing. Ignores the time window. Not the "
             "same as --force, which performs a real run.",
    )
    args = parser.parse_args()

    now_ist = datetime.now(IST)

    if args.dry_run:
        db = SessionLocal()
        try:
            preview = preview_daily_reminders(db, now_ist.date())
        finally:
            db.close()
        print(f"DRY RUN as of {now_ist.isoformat()} (IST) -- preview only, nothing written, nothing sent.")
        print("This is a snapshot of eligibility right now, using today's date -- it approximates the")
        print("next scheduled run (or a --force run), but due dates, ownership and settings can change")
        print("before that run actually fires. Re-run --dry-run just before relying on this.")
        if not preview.recipients:
            print("  No one would be notified right now.")
        for r in preview.recipients:
            parts = []
            if r.reminder_count:
                parts.append(f"{r.reminder_count} reminder(s)")
            if r.access_mismatch_count:
                parts.append(f"{r.access_mismatch_count} access-mismatch escalation(s)")
            if r.overdue_escalation_count:
                parts.append(f"{r.overdue_escalation_count} overdue escalation(s)")
            if r.exhausted_count:
                parts.append(f"{r.exhausted_count} already exhausted, will NOT retry")
            no_email_note = "" if r.would_email else " -- no email on file, in-app only"
            print(f"  {r.name} ({r.email or 'no email on file'}){no_email_note}: {', '.join(parts) or 'nothing new'}")
        print(
            f"  Total recipients: {len(preview.recipients)}; "
            f"total items to be included in a digest: {preview.total_notifications}; "
            f"already exhausted (visible in delivery-failures, will not retry): {preview.total_exhausted}"
        )
        return

    if not args.force and not _in_window(now_ist):
        print(f"Outside the 09:00-09:30 Asia/Kolkata window (now {now_ist.isoformat()}) -- nothing to do.")
        return

    db = SessionLocal()
    try:
        result = run_daily_reminders(db, now_ist.date())
    finally:
        db.close()

    print(f"Run for {now_ist.date().isoformat()} (IST), invoked at {now_ist.isoformat()}:")
    print(f"  Owners notified:                {result.owners_notified}")
    print(f"  Reminder notifications created: {result.reminder_notifications_created}")
    print(f"  Access-mismatch escalations:    {result.access_mismatches_escalated}")
    print(f"  Overdue-threshold escalations:  {result.overdue_escalations_created}")
    print(f"  Digest emails sent:             {result.digest_emails_sent}")
    print(f"  Digest emails failed:           {result.digest_emails_failed}")
    if result.skipped_owners_no_email:
        print(f"  Owners skipped (no email on file): {', '.join(result.skipped_owners_no_email)}")


if __name__ == "__main__":
    main()
