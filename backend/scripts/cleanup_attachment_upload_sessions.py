"""P4 contract v7, Section 4/6: the chunked-upload cleanup run. Invoked by an OS-level crontab
entry (this app has no in-process scheduler -- same precedent as
send_daily_follow_up_reminders.py / deploy/backup_db.sh).

Five sweeps, every run (see app.core.attachment_upload.run_cleanup for the full guarantees each
one keeps):
  0. Stuck sessions (completing, idle > 5 min) recovered -- the token (completion_attempt) is
     bumped in the SAME statement as the status reset back to uploading, with no gap where a
     stale worker's old token is still valid (revision 7 fix). Also triggered lazily, on a
     client's own retry, so this proactive sweep is a safety net, not the only path to recovery.
  1. Abandoned sessions (uploading, idle > 24h) -- claimed atomically, temp files and rows
     deleted. No Attachment was ever created for these; nothing is lost.
  2. Completed sessions whose temp_files_purged_at is still NULL -- retries the synchronous
     temp-chunk deletion that should have followed completion; never touches the session row,
     resulting_attachment_id, or the committed Attachment's own file.
  3. Orphaned attempt-specific temp files (a superseded chunk-write or assembly attempt that
     never promoted) -- never touches an accepted/promoted file.
  4. Orphaned final-path files (v7's own fix): a file finalization placed at its deterministic
     final path whose database commit never happened. Deleted ONLY when its attempt is
     irrevocably superseded AND a fresh check against `attachments` finds no row referencing
     it -- a committed Attachment's own file can never be reached by this sweep.

No time window to wait for (unlike the reminder job) -- safe, and intended, to run on a short
interval (proposed: every 15 minutes, matching this codebase's own existing cron precedent).

--dry-run reports exactly what each sweep would do -- how many sessions/files -- without deleting
or modifying anything, reusing the real run's own selection criteria for every sweep (never a
hand-written approximation), matching this codebase's own established dry-run convention."""

import argparse
from datetime import UTC, datetime

from app.core.attachment_upload import run_cleanup
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read-only preview: counts what each of the four sweeps would do -- deletes and "
             "modifies nothing. Reuses each sweep's own real selection criteria.",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print ONE JSON line of storage health (open sessions, declared bytes, oldest open session, stored bytes "
             "vs the cap, quarantined files) for monitoring, and run no cleanup.",
    )
    args = parser.parse_args()

    if args.report:
        import json

        from app.core.upload_policy import storage_health

        db = SessionLocal()
        try:
            print(json.dumps({"at": datetime.now(UTC).isoformat(), **storage_health(db)}))
        finally:
            db.close()
        return

    now = datetime.now(UTC)
    db = SessionLocal()
    try:
        result = run_cleanup(db, dry_run=args.dry_run)
    finally:
        db.close()

    if args.dry_run:
        print(f"DRY RUN at {now.isoformat()} -- preview only, nothing written, nothing deleted:")
        print(f"  Stuck sessions that WOULD be recovered (token reset):     {result['stuck_sessions_recovered']}")
        print(f"  Abandoned sessions that WOULD be purged:                  {result['abandoned_sessions_purged']}")
        print(f"  Completed sessions' temp files that WOULD be purged:      {result['completed_sessions_temp_purged']}")
        print(f"  Orphaned attempt-specific temp files that WOULD be removed: {result['orphaned_attempt_temp_files_removed']}")
        print(f"  Orphaned final-path files that WOULD be removed:          {result['orphaned_final_path_files_removed']}")
    else:
        print(f"Run at {now.isoformat()}:")
        print(f"  Stuck sessions recovered (token reset):        {result['stuck_sessions_recovered']}")
        print(f"  Abandoned sessions purged:                     {result['abandoned_sessions_purged']}")
        print(f"  Completed sessions' temp files purged:         {result['completed_sessions_temp_purged']}")
        print(f"  Orphaned attempt-specific temp files removed:  {result['orphaned_attempt_temp_files_removed']}")
        print(f"  Orphaned final-path files removed:             {result['orphaned_final_path_files_removed']}")


if __name__ == "__main__":
    main()
