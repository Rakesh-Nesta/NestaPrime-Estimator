# Deploying to the Lightsail production server

Target: Ubuntu 24.04, static IP `65.1.234.78`, Docker + nginx already installed, 2GB RAM.
Everything below is meant to be pasted into the Lightsail browser SSH terminal, in order.
No SSH key setup needed -- the browser terminal is already a shell on the box.

Docker runs the backend + Postgres. nginx (already installed on the host, not
containerized) serves the frontend's static build and reverse-proxies `/api/*` to the
backend container. The frontend itself is also built via Docker (a build-only image,
`frontend/Dockerfile`) so the server never needs Node.js installed -- only Docker, which
it already has.

## 1. Get the repo onto the server

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Rakesh-Nesta/NestaPrime-Estimator.git
cd NestaPrime-Estimator
```

If the repo is private, this will prompt for GitHub credentials -- use a personal access
token as the password, not your GitHub account password.

**Prerequisites this depends on** (already installed on the current server as of
11 Sep 2026 -- listed here so a rebuild or a second server doesn't have to
rediscover this the hard way):

- **`docker-compose-v2`** -- `docker compose` (the space, not `docker-compose` the
  old hyphenated binary) needs this package specifically. Check with `docker compose
  version`; if that errors, `sudo apt-get install -y docker-compose-v2`.
- **`docker buildx`** -- step 6 below uses `docker build --output`, which the legacy
  (non-buildx) builder does not support at all -- it fails outright, not with a
  helpful message. Check with `docker buildx version`; if missing, `sudo apt-get
  install -y docker-buildx` (matching `docker.io`'s own Ubuntu package naming --
  this server's Docker came from Ubuntu's `docker.io` package, not Docker Inc.'s
  own apt repo, which would instead name this `docker-buildx-plugin`).

## 2. Generate secrets and write the server's `.env`

This `.env` is read automatically by `docker compose` and is **never committed** --
`.gitignore` already excludes it. Generate real random values, don't reuse the ones shown
here:

```bash
POSTGRES_PW=$(openssl rand -base64 24)
JWT_SECRET=$(openssl rand -hex 32)

cat > .env <<EOF
POSTGRES_PASSWORD=${POSTGRES_PW}
DATABASE_URL=postgresql+psycopg://nestaprime:${POSTGRES_PW}@db:5432/nestaprime_estimator
SECRET_KEY=${JWT_SECRET}
CORS_ORIGINS=http://65.1.234.78
EOF

echo "Wrote .env -- Postgres password and JWT secret generated, not shown above on purpose."
```

## 3. Build and start the backend + database

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds the backend image, starts Postgres, waits for its healthcheck, then starts
the backend (which runs `alembic upgrade head` on every start -- safe, since re-running
migrations that are already applied is a no-op). Watch it come up:

```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

Press Ctrl+C once you see `Application startup complete` / gunicorn's `Booting worker`
lines. Then confirm it's actually answering:

```bash
curl http://127.0.0.1:8000/health
```

Expect `{"status":"ok"}`. If this hangs or errors, the backend container isn't up --
check `docker compose -f docker-compose.prod.yml ps` and `docker compose -f
docker-compose.prod.yml logs backend` before continuing.

## 4. Seed reference data and the first Director account

A fresh database has schema but no data -- no sports, no scope items, no rate
categories. Nothing in the app works until this step runs (confirmed locally: the sport
picker is empty without it). This only needs to run once, ever:

```bash
docker compose -f docker-compose.prod.yml exec -e PYTHONPATH=/app backend sh -c '
for s in seed_regional_multipliers seed_sports seed_scope_items seed_labour_categories \
         seed_netting_grades seed_flooring_guides seed_lighting_standards \
         seed_accessory_catalog seed_margin_policies seed_settings; do
  echo "--- $s ---"
  python scripts/$s.py
done
'
```

`PYTHONPATH=/app` matters here: `python scripts/foo.py` runs with `/app/scripts` as
`sys.path[0]`, not `/app` itself, so `from app.core... import ...` inside the script
fails with `ModuleNotFoundError: No module named 'app'` without it. Every one-off
script invocation in this runbook needs this same flag -- it's not specific to any
one script.

Each line should say how many rows it seeded (30 sports, 30 scope items, etc.) -- `0
already existed` on a second run is expected and harmless, not an error.

Now create the one real admin account you'll actually log in with. Everyone else gets
created from inside the app afterward (Master Settings -> User management), not by
script -- that's the point of yesterday's User Management feature.

```bash
docker compose -f docker-compose.prod.yml exec \
  -e PYTHONPATH=/app \
  -e INITIAL_DIRECTOR_EMAIL="you@yourcompany.com" \
  -e INITIAL_DIRECTOR_PASSWORD="pick-a-real-password-here" \
  backend python scripts/seed_initial_director.py
```

Replace both values first. This account is forced to change its password on first
login (the same guarantee every account created through the app gets) -- so the value
you type here only needs to get you logged in once.

## 5. Build the frontend and hand it to nginx

```bash
sudo mkdir -p /var/www/nestaprime
docker build -f frontend/Dockerfile --target export \
  --build-arg VITE_API_URL=http://65.1.234.78/api \
  --output /tmp/nestaprime-frontend \
  frontend
sudo cp -r /tmp/nestaprime-frontend/dist/. /var/www/nestaprime/dist/
sudo chmod -R 755 /var/www/nestaprime
```

The `chmod` matters: nginx runs as `www-data`, not root, and `sudo cp` alone can
leave the copied tree without the read/execute permissions `www-data` needs -- if
this step is skipped, nginx serves 403 Forbidden for every file even though the
config and the files themselves are both correct.

`VITE_API_URL` is baked into the build at this step, not read at runtime -- if the
server's IP or domain ever changes, this build step has to be rerun, restarting nginx
alone won't pick it up.

## 6. Point nginx at it

```bash
sudo cp deploy/nginx/nestaprime.conf /etc/nginx/sites-available/nestaprime
sudo ln -sf /etc/nginx/sites-available/nestaprime /etc/nginx/sites-enabled/nestaprime
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` validates the config before reloading -- if it errors, nginx keeps running
the old config rather than going down, so it's safe to fix and retry.

**One-time fix needed on the already-deployed server (12 Sep 2026):** the reference
config above didn't set `client_max_body_size`, so nginx's own 1 MB default silently
413'd any upload past that -- smaller than both app-level upload limits (Company Logo's
5 MB, M.3 Attachments' 100 MB), found live trying to upload a ~2 MB company logo. Fixed
in the repo's `deploy/nginx/nestaprime.conf`; re-run this step's three commands on the
server once to pick it up -- this is exactly the case the file's own comment above
("nginx config all persist[s]" across a redeploy) doesn't cover, since it never re-copies
an already-deployed config on its own.

## 7. Smoke test

```bash
curl http://65.1.234.78/api/health
```

Expect `{"status":"ok"}`. Then in a real browser: go to `http://65.1.234.78`, log in
with the Director account from step 4, create a project, add any sport, build and
verify its Cost Sheet, and create an Estimate option. This exact sequence was verified
locally against these same Docker images before this was handed to you -- if it doesn't
work here, something about the server environment differs from local (check `docker
compose -f docker-compose.prod.yml logs backend` and the nginx error log at
`/var/log/nginx/error.log` first).

## Redeploying after a code change

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build backend
# Only if the frontend changed:
docker build -f frontend/Dockerfile --target export \
  --build-arg VITE_API_URL=http://65.1.234.78/api \
  --output /tmp/nestaprime-frontend frontend
sudo cp -r /tmp/nestaprime-frontend/dist/. /var/www/nestaprime/dist/
sudo chmod -R 755 /var/www/nestaprime
```

No need to redo steps 2, 4, or 6 -- secrets, seed data, and the nginx config all persist.

## What's deliberately not here yet

- **HTTPS** -- serving plain HTTP on the IP directly; no domain name to get a TLS cert
  against yet. Worth revisiting once there's a domain pointed at this IP (`certbot
  --nginx` is the usual path).
- **Automated backups of the `pgdata_prod` volume** -- the AWS-side snapshot mentioned
  as already set up covers the instance, but doesn't know to quiesce Postgres first: a
  snapshot taken mid-write is not the same guarantee as a real `pg_dump`. Worth a cron
  job running `docker compose -f docker-compose.prod.yml exec db pg_dump ...` to a
  separate location.
- **A process supervisor restarting the stack on server reboot** -- `restart:
  unless-stopped` in the compose file brings containers back after a Docker daemon
  restart, but nothing currently re-runs `docker compose up` after a full server reboot
  automatically (a systemd unit or `docker compose` running via `crontab -e` with
  `@reboot` would close this).
