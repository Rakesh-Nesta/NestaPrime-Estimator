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

--force bypasses the time-window check (for a manual/ops re-run, or this session's own live
verification) but never bypasses the per-notification idempotency itself -- it cannot cause a
duplicate send for something already successfully delivered today.
"""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.reminders import run_daily_reminders
from app.db.session import SessionLocal

IST = ZoneInfo("Asia/Kolkata")
WINDOW_START_MINUTES = 9 * 60  # 09:00
WINDOW_END_MINUTES = 9 * 60 + 30  # 09:30


def _in_window(now_ist: datetime) -> bool:
    minutes = now_ist.hour * 60 + now_ist.minute
    return WINDOW_START_MINUTES <= minutes < WINDOW_END_MINUTES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Run now regardless of the 09:00-09:30 IST window.")
    args = parser.parse_args()

    now_ist = datetime.now(IST)
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
