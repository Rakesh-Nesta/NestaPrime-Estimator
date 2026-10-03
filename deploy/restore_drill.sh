#!/usr/bin/env bash
# Note R2 (Annexure 2): "A backup never restored is a hope, not a backup."
#
# The pg_dump half of the quarterly restore drill (see deploy/README.md's
# "Backups & restore drill" section for the other half -- restoring an
# actual Lightsail instance snapshot). This script never touches the real
# database: it spins up a throwaway, isolated postgres:16 container,
# restores one backup_db.sh dump into it, runs a few sanity checks, then
# tears the container down -- safe to run as many times as you like,
# including against production's own latest dump, without any risk to
# anything live.
#
# Usage: ./restore_drill.sh path/to/nestaprime_estimator_TIMESTAMP.sql.gz
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 path/to/nestaprime_estimator_TIMESTAMP.sql.gz" >&2
  exit 1
fi
DUMP_FILE="$1"
if [ ! -f "$DUMP_FILE" ]; then
  echo "No such file: $DUMP_FILE" >&2
  exit 1
fi

CONTAINER_NAME="nestaprime-restore-drill-$$"
DRILL_PASSWORD="drill-only-$(date +%s)"

cleanup() {
  echo "[$(date -u +%FT%TZ)] Tearing down drill container"
  docker rm -f "$CONTAINER_NAME" > /dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[$(date -u +%FT%TZ)] Starting a throwaway postgres:16 container for the drill"
docker run -d --name "$CONTAINER_NAME" \
  -e POSTGRES_USER=nestaprime -e POSTGRES_PASSWORD="$DRILL_PASSWORD" -e POSTGRES_DB=nestaprime_estimator \
  postgres:16 > /dev/null

echo "[$(date -u +%FT%TZ)] Waiting for it to accept connections"
for _ in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" pg_isready -U nestaprime > /dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! docker exec "$CONTAINER_NAME" pg_isready -U nestaprime > /dev/null 2>&1; then
  echo "Drill container never became ready -- aborting" >&2
  exit 1
fi

echo "[$(date -u +%FT%TZ)] Restoring $DUMP_FILE into it"
gunzip -c "$DUMP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -v ON_ERROR_STOP=1 > /dev/null

echo "[$(date -u +%FT%TZ)] Restore completed without error. Sanity-checking table row counts:"
docker exec "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -t -c "
  SELECT table_name, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I', table_name), false, true, '')))[1]::text::int AS row_count
  FROM information_schema.tables
  WHERE table_schema = 'public'
  ORDER BY table_name;
"

USER_COUNT=$(docker exec "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -t -A -c "SELECT count(*) FROM users;" 2>/dev/null || echo "0")
SPORT_COUNT=$(docker exec "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -t -A -c "SELECT count(*) FROM sports;" 2>/dev/null || echo "0")

# P5: the migration marker is the legacy-adoption cutoff and must come back EXACTLY as it was. Expected value, in
# order of preference: EXPECTED_P5_MARKER_DEPLOYED_AT (operator-supplied), else the .p5marker sidecar that
# backup_db.sh wrote next to the dump ("none" = the source database predates P5 and had no marker).
SIDECAR="${DUMP_FILE%.sql.gz}.p5marker"
EXPECTED_MARKER="${EXPECTED_P5_MARKER_DEPLOYED_AT:-}"
if [ -z "$EXPECTED_MARKER" ] && [ -f "$SIDECAR" ]; then
  EXPECTED_MARKER="$(tr -d '[:space:]' < "$SIDECAR")"
fi
MARKER_PRESENT=$(docker exec "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -t -A -c "SELECT to_regclass('public.p5_migration_marker') IS NOT NULL;" 2>/dev/null || echo "f")
MARKER_FAIL=""
if [ "$MARKER_PRESENT" = "t" ]; then
  MARKER_ROWS=$(docker exec "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -t -A -c "SELECT count(*) FROM p5_migration_marker;")
  MARKER_VALUE=$(docker exec "$CONTAINER_NAME" psql -U nestaprime -d nestaprime_estimator -t -A -c "SELECT to_char(deployed_at, 'YYYY-MM-DD\"T\"HH24:MI:SS.US') FROM p5_migration_marker WHERE id = 1;")
  if [ "$MARKER_ROWS" != "1" ] || [ -z "$MARKER_VALUE" ]; then
    MARKER_FAIL="p5_migration_marker came back with $MARKER_ROWS row(s) and no id=1 value -- the legacy-adoption cutoff did not survive"
  elif [ -n "$EXPECTED_MARKER" ] && [ "$EXPECTED_MARKER" != "none" ] && [ "$EXPECTED_MARKER" != "$MARKER_VALUE" ]; then
    MARKER_FAIL="p5_migration_marker restored as $MARKER_VALUE but the original was $EXPECTED_MARKER"
  elif [ "$EXPECTED_MARKER" = "none" ]; then
    MARKER_FAIL="the source database had no p5_migration_marker but the restore contains one ($MARKER_VALUE)"
  fi
  echo "[$(date -u +%FT%TZ)] P5 marker: $MARKER_VALUE (expected: ${EXPECTED_MARKER:-not recorded -- only checked that exactly one id=1 row exists})"
else
  if [ -n "$EXPECTED_MARKER" ] && [ "$EXPECTED_MARKER" != "none" ]; then
    MARKER_FAIL="the source database had a p5_migration_marker ($EXPECTED_MARKER) but the restore has no such table"
  fi
  echo "[$(date -u +%FT%TZ)] P5 marker: table not present in this dump (expected: ${EXPECTED_MARKER:-none recorded})"
fi
if [ -n "$MARKER_FAIL" ]; then
  echo "FAIL: $MARKER_FAIL. Do not promote this restore -- an upgrade would be unable to reuse the original cutoff." >&2
  exit 1
fi

echo ""
echo "[$(date -u +%FT%TZ)] Drill result: users=$USER_COUNT sports=$SPORT_COUNT"
if [ "$USER_COUNT" -gt 0 ] && [ "$SPORT_COUNT" -gt 0 ]; then
  echo "PASS: dump restores cleanly and contains real data (see docs/ops/restore-drill-log.md to record this)."
  exit 0
else
  echo "FAIL: restore completed but users/sports came back empty -- this dump would not actually recover the app. Investigate before trusting it." >&2
  exit 1
fi
