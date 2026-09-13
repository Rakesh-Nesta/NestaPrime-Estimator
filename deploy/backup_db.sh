#!/usr/bin/env bash
# Note R2 (Annexure 2): "A backup never restored is a hope, not a backup."
#
# Lightsail's own daily instance snapshot (already configured, per
# deploy/README.md) covers this server's whole disk -- but it doesn't
# quiesce Postgres first, so a snapshot taken mid-write is not the same
# guarantee as a real pg_dump. This script writes a consistent,
# point-in-time pg_dump to local disk on a schedule (see deploy/README.md
# for the cron entry) *before* that snapshot runs each night, so the
# snapshot always captures a restorable dump file alongside the raw
# (possibly-inconsistent) live data directory -- no new off-instance
# storage or AWS credentials needed.
#
# Usage: ./backup_db.sh [backup_dir] [retention_count]
#   backup_dir       default: /home/*/nestaprime-backups (see BACKUP_DIR below)
#   retention_count  default: 14 (keep the last 14 dumps -- two weeks at a
#                     nightly cadence, so a drill has more than one recent
#                     dump to fall back to if the newest happens to be bad)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.prod.yml"

BACKUP_DIR="${1:-$HOME/nestaprime-backups}"
RETENTION_COUNT="${2:-14}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_DIR/nestaprime_estimator_${TIMESTAMP}.sql.gz"
TMP_DEST="${DEST}.tmp"

echo "[$(date -u +%FT%TZ)] Starting pg_dump -> $DEST"

# -T (no pseudo-tty) is required for exec output to pipe cleanly. Custom
# format would need pg_restore's own tooling on the far end of a drill;
# plain SQL + gzip keeps the restore side to nothing but `gunzip | psql`,
# the same two commands anyone doing the drill already has.
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U nestaprime --no-owner --no-privileges nestaprime_estimator \
  | gzip > "$TMP_DEST"

# Sanity check before it replaces anything: a zero-byte or truncated dump
# is worse than no backup at all if it silently ages out a good one via
# the retention sweep below.
if [ ! -s "$TMP_DEST" ] || ! gzip -t "$TMP_DEST" 2>/dev/null; then
  echo "[$(date -u +%FT%TZ)] pg_dump produced an empty or corrupt file -- aborting, not replacing any existing backup" >&2
  rm -f "$TMP_DEST"
  exit 1
fi

mv "$TMP_DEST" "$DEST"
echo "[$(date -u +%FT%TZ)] Wrote $(du -h "$DEST" | cut -f1) to $DEST"

# Retention: keep the newest $RETENTION_COUNT, delete the rest.
mapfile -t OLD_BACKUPS < <(ls -1t "$BACKUP_DIR"/nestaprime_estimator_*.sql.gz 2>/dev/null | tail -n "+$((RETENTION_COUNT + 1))")
if [ "${#OLD_BACKUPS[@]}" -gt 0 ]; then
  echo "[$(date -u +%FT%TZ)] Pruning ${#OLD_BACKUPS[@]} backup(s) older than the newest $RETENTION_COUNT"
  rm -f "${OLD_BACKUPS[@]}"
fi

echo "[$(date -u +%FT%TZ)] Done. $(ls -1 "$BACKUP_DIR"/nestaprime_estimator_*.sql.gz 2>/dev/null | wc -l) backup(s) on disk."
