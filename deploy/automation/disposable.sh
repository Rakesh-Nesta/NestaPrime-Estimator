#!/usr/bin/env bash
# No live targets; all containers/volumes have a unique disposable prefix.
set -euo pipefail
cd "$(dirname "$0")/../.."
name="np-release-test-$(date +%s)-$$"
tmp=$(mktemp -d)
cleanup() {
  result=$?
  if [ "$result" -ne 0 ]; then
    echo "FAIL: disposable release verification exited $result; container state and last 80 log lines follow" >&2
    for service in db restore app web; do
      echo "--- disposable $service ---" >&2
      docker inspect --format '{{json .State}}' "$name-$service" >&2 || true
      docker logs --tail 80 "$name-$service" >&2 || true
    done
    for log in build.log frontend.log; do
      if [ -f "$tmp/$log" ]; then
        echo "--- disposable $log ---" >&2
        tail -80 "$tmp/$log" >&2
      fi
    done
  fi
  docker rm -f "$name-db" "$name-restore" "$name-app" "$name-web" >/dev/null 2>&1 || true
  docker network rm "$name" >/dev/null 2>&1 || true
  docker image rm "$name:backend" >/dev/null 2>&1 || true
  rm -rf "$tmp"
  exit "$result"
}
trap cleanup EXIT
python3 -m unittest discover -s deploy/automation -p 'test_*.py'
docker network create "$name" >/dev/null
for db in db restore; do
  docker run -d --name "$name-$db" --network "$name" -e POSTGRES_USER=nestaprime -e POSTGRES_PASSWORD=disposable-only -e POSTGRES_DB=nestaprime_estimator postgres:16 >/dev/null
  for attempt in $(seq 1 60); do
    if timeout 2 docker exec "$name-$db" pg_isready -U nestaprime >/dev/null 2>&1; then break; fi
    sleep 1
  done
  timeout 2 docker exec "$name-$db" pg_isready -U nestaprime
done
docker build -t "$name:backend" . > "$tmp/build.log" 2>&1
id=$(docker inspect -f '{{.Id}}' "$name:backend")
docker save "$id" > "$tmp/backend.tar"
docker load -i "$tmp/backend.tar" >/dev/null
test "$(docker inspect -f '{{.Id}}' "$name:backend")" = "$id"
docker run -d --name "$name-app" --network "$name" -p 0.0.0.0::8000 -e DATABASE_URL="postgresql+psycopg://nestaprime:disposable-only@$name-db:5432/nestaprime_estimator" -e SECRET_KEY=disposable-test-only -e ENVIRONMENT=development "$id" >/dev/null
port=$(docker port "$name-app" 8000 | head -1 | cut -d: -f2)
python3 deploy/automation/wait_http.py "http://${TEST_DOCKER_HOST:-127.0.0.1}:$port/health" --kind health --timeout 180 --output "$tmp/health.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"] == "ok"' "$tmp/health.json"
docker exec "$name-db" pg_dump -U nestaprime -Fc nestaprime_estimator > "$tmp/database.dump"
docker exec -i "$name-restore" pg_restore -U nestaprime -d nestaprime_estimator --exit-on-error < "$tmp/database.dump"
for db in db restore; do
  docker exec "$name-$db" psql -U nestaprime -d nestaprime_estimator -Atc 'SELECT version_num FROM alembic_version' > "$tmp/$db.revision"
  docker exec "$name-$db" psql -U nestaprime -d nestaprime_estimator -Atc 'SELECT id,deployed_at FROM p5_migration_marker' > "$tmp/$db.marker"
done
cmp "$tmp/db.revision" "$tmp/restore.revision"
cmp "$tmp/db.marker" "$tmp/restore.marker"
docker build -f frontend/Dockerfile --target export --build-arg VITE_API_URL=/api --output "type=local,dest=$tmp/frontend" frontend > "$tmp/frontend.log" 2>&1
docker run -d --name "$name-web" -p 0.0.0.0::80 nginx:alpine >/dev/null
docker cp "$tmp/frontend/dist/." "$name-web:/usr/share/nginx/html/"
port=$(docker port "$name-web" 80 | head -1 | cut -d: -f2)
python3 deploy/automation/wait_http.py "http://${TEST_DOCKER_HOST:-127.0.0.1}:$port/" --kind frontend --expected-file "$tmp/frontend/dist/index.html" --timeout 60 --output "$tmp/served.html"
cmp "$tmp/served.html" "$tmp/frontend/dist/index.html"
docker run --rm --entrypoint python "$id" -m pip list --format=freeze > "$tmp/packages.txt"
echo 'PASS: exact image reload, migration startup, health, whole DB restore, original P5 marker, built frontend served by nginx.'
