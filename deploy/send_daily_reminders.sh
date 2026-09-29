#!/usr/bin/env bash
# WP8 (correction plan, 2026-09-29): the daily 9:00 Asia/Kolkata follow-up reminder run.
#
# This app has no in-process scheduler (same reasoning as deploy/backup_db.sh's own
# comment) -- an OS-level crontab entry invokes this wrapper, which runs the Python script
# inside the same `backend` container everything else already runs in (see deploy/README.md
# for the exact cron entry). Invoked every 15 minutes rather than once a day: the script
# itself computes Asia/Kolkata time via zoneinfo (never trusting the server's own OS
# timezone) and only does real work inside the 09:00-09:30 IST window, using its own
# per-notification idempotency to make repeated ticks inside that window safe -- this is what
# lets a later tick retry anything an earlier tick in the same window didn't finish, with no
# risk of double-sending anything that already succeeded.
#
# Usage: ./send_daily_reminders.sh [--force]
#   --force  bypass the time-window check (a manual/ops re-run) -- still cannot cause a
#            duplicate send for something already delivered today; passed straight through.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.prod.yml"

docker compose -f "$COMPOSE_FILE" exec -T backend \
  python scripts/send_daily_follow_up_reminders.py "$@"
