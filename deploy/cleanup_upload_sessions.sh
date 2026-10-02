#!/usr/bin/env bash
# Upload hardening: the scheduled cleanup of abandoned resumable-upload sessions, with a monitoring heartbeat.
#
# NOT scheduled by default -- activating it is a separate, deliberate ops step (see "Upload cleanup" in
# deploy/README.md for the proposed crontab line). Running it by hand is safe at any time.
#
# What it does: runs scripts/cleanup_attachment_upload_sessions.py inside the running `backend` container
# (abandoned sessions purged, which RELEASES the per-user open-session / declared-byte quota they were holding),
# then prints one JSON line of storage health (open sessions, declared bytes, oldest open session, stored bytes vs
# cap, quarantined files). On success it records a heartbeat file with the time of the last good run so monitoring
# can alert when the job has silently stopped (the file's age) or when its numbers drift.
#
# Usage: ./cleanup_upload_sessions.sh [--dry-run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.prod.yml"
HEARTBEAT="${UPLOAD_CLEANUP_HEARTBEAT:-$HOME/nestaprime-backups/upload-cleanup.heartbeat}"

docker compose -f "$COMPOSE_FILE" exec -T backend python scripts/cleanup_attachment_upload_sessions.py "$@"
docker compose -f "$COMPOSE_FILE" exec -T backend python scripts/cleanup_attachment_upload_sessions.py --report \
  | tee "$HEARTBEAT.tmp"
case " $* " in
  *" --dry-run "*) rm -f "$HEARTBEAT.tmp" ;;           # a preview is not a run
  *) mv "$HEARTBEAT.tmp" "$HEARTBEAT" ;;
esac
