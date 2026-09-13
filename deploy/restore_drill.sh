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

echo ""
echo "[$(date -u +%FT%TZ)] Drill result: users=$USER_COUNT sports=$SPORT_COUNT"
if [ "$USER_COUNT" -gt 0 ] && [ "$SPORT_COUNT" -gt 0 ]; then
  echo "PASS: dump restores cleanly and contains real data (see docs/ops/restore-drill-log.md to record this)."
  exit 0
else
  echo "FAIL: restore completed but users/sports came back empty -- this dump would not actually recover the app. Investigate before trusting it." >&2
  exit 1
fi
