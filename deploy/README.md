# Deploying to the Lightsail production server

Target: Ubuntu 24.04, static IP `65.1.234.78`, Docker + nginx already installed, 2GB RAM.
Served over **HTTPS on a domain** (Amendment 55): everywhere below, `your.domain.example` stands for the
real domain. A server still on plain HTTP by IP follows **"Cutover to HTTPS"** (further down) once.
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
CORS_ORIGINS=https://your.domain.example
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

**The first Admin (Amendment 59, Section 62).** An Admin runs the system -- people, access, company identity,
templates -- so the Director does not have to. Only an Admin creates another Admin, so the first one comes from
outside the app, once, with the **real email address of the person**:

```bash
docker compose -f docker-compose.prod.yml exec -T \
  -e PYTHONPATH=/app \
  -e INITIAL_ADMIN_EMAIL="the-real-address@theircompany.in" \
  backend python scripts/seed_initial_admin.py
```

Replace the address first. The temporary password is **generated and printed once, on your terminal only** -- give it
to the person privately; they must change it at first sign-in. There is no password to type or paste. The script
refuses anything that does not look like an email address, refuses placeholder addresses (`example.com`,
`yourcompany.com`, ...), refuses if an active Admin already exists, and never creates a duplicate.

*What went wrong the first time (26 September 2026):* the earlier version of this step, with its placeholder words left
in, created an Admin called `THEIR-EMAIL` with a password that had been written in a chat. It was deleted within minutes
(`DELETE FROM users WHERE email = 'THEIR-EMAIL' AND role = 'ADMIN'`, once, after looking) and the script was changed so
it cannot happen again.

## 5. Build the frontend and hand it to nginx

```bash
sudo mkdir -p /var/www/nestaprime
docker build -f frontend/Dockerfile --target export \
  --build-arg VITE_API_URL=https://your.domain.example/api \
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

**On a fresh server the certificate does not exist yet**, so this happens in two steps -- the
bootstrap config first, then (after certbot) the final one. Follow **"Cutover to HTTPS"** below;
its steps 2 to 5 are this step. (`deploy/nginx/nestaprime.conf` carries a `__DOMAIN__` placeholder and
must be installed through the `sed` line in that section, never copied as it is.)

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
curl https://your.domain.example/api/health
```

Expect `{"status":"ok"}`. Then in a real browser: go to `https://your.domain.example`, log in
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
  --build-arg VITE_API_URL=https://your.domain.example/api \
  --output /tmp/nestaprime-frontend frontend
sudo cp -r /tmp/nestaprime-frontend/dist/. /var/www/nestaprime/dist/
sudo chmod -R 755 /var/www/nestaprime
```

No need to redo steps 2, 4, or 6 -- secrets, the *original* seed data (Part 4's reference
data and first Director account), and the nginx config all persist.

**But check whether this specific PR added a new one-off seed script or new rows to an
existing seed constant.** A migration landing cleanly (it runs automatically on backend
container start) says nothing about whether a PR's `scripts/seed_*.py` also ran --
that's a separate, manual step this redeploy sequence does not do for you. Found the
hard way on 2026-09-15 (see `docs/ops/deploy-log.md`): Amendment 11's schema migration
went out fine, but its seed data (`seed_labour_categories.py`, `seed_rate_items.py`)
sat unrun on production for hours until a restore drill caught it. If the PR touched
`app/seed_data.py` or added a `scripts/seed_*.py` call, run it now:
```bash
docker compose -f docker-compose.prod.yml exec -T -e PYTHONPATH=/app backend python scripts/seed_<name>.py
```
Every script here is re-run-safe (skips anything that already exists by its natural
key), so running one that turns out not to be needed is harmless.

## Cutover to HTTPS (one time; Amendment 55, Section 59)

For a server that is still plain HTTP on the bare IP. Run each numbered step in order; every command
block is its own step -- **give the `sudo cp` frontend copy its own block and check the served bundle
afterwards**. Check each step from outside before the next. `your.domain.example` is the real domain.

**0. Before anything (Director).** (a) Add a DNS `A` record for the domain pointing at `65.1.234.78` and
confirm it resolves. (b) In the Lightsail console, Networking tab, open **TCP 443** (port 80 stays open).
(c) If WhatsApp/Telegram callbacks are configured, check none targets `http://65.1.234.78/...` -- a
redirect would break it; point it at the HTTPS domain, or at loopback if it runs on this host.

```bash
getent hosts your.domain.example
```

**1. Keep the way back.**

```bash
sudo cp /etc/nginx/sites-available/nestaprime /etc/nginx/sites-available/nestaprime.pre-https
```

**2. Install certbot and the webroot folder.**

```bash
sudo apt-get update && sudo apt-get install -y certbot
sudo mkdir -p /var/www/certbot
```

**3. Bootstrap config (HTTP only; the app keeps working), then get the certificate.**

```bash
cd /home/ubuntu/NestaPrime-Estimator && git pull
sed "s/__DOMAIN__/your.domain.example/g" deploy/nginx/nestaprime-bootstrap.conf | sudo tee /etc/nginx/sites-available/nestaprime > /dev/null
sudo nginx -t && sudo systemctl reload nginx
```

```bash
sudo certbot certonly --webroot -w /var/www/certbot -d your.domain.example
```

Expect "Successfully received certificate". If it fails, nothing has changed for users -- the site is
still the old HTTP one; fix the DNS/port cause and rerun this step.

**4. Point the backend at the HTTPS origin and rebuild it** (the forwarded-headers change ships in the
same rebuild):

```bash
sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://your.domain.example|' .env
docker compose -f docker-compose.prod.yml up -d --build backend
```

**5. Install the final config.** `nginx -t` is the gate; if it errors, nothing has changed.

```bash
sed "s/__DOMAIN__/your.domain.example/g" deploy/nginx/nestaprime.conf | sudo tee /etc/nginx/sites-available/nestaprime > /dev/null
sudo nginx -t && sudo systemctl reload nginx
```

**6. Rebuild the frontend for the HTTPS address and copy it -- the copy as its own step.**

```bash
docker build -f frontend/Dockerfile --target export --build-arg VITE_API_URL=https://your.domain.example/api --output /tmp/nestaprime-frontend frontend
```

```bash
sudo cp -r /tmp/nestaprime-frontend/dist/. /var/www/nestaprime/dist/ && sudo chmod -R 755 /var/www/nestaprime
```

**7. Renewal.** Certificates last 90 days; certbot installs a systemd timer that renews them. Prove it:

```bash
sudo certbot renew --dry-run
systemctl list-timers | grep certbot
```

The renewal replaces the certificate files but nginx must reload to use them -- certbot's own deploy
hook does not do that here, so add one:

```bash
printf '#!/bin/sh\nsystemctl reload nginx\n' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh > /dev/null
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

**Rollback (any time up to and including step 6).** Restore the kept config, reload, and rebuild the
frontend for the old address; the site is then the plain-HTTP one again:

```bash
sudo cp /etc/nginx/sites-available/nestaprime.pre-https /etc/nginx/sites-available/nestaprime
sudo nginx -t && sudo systemctl reload nginx
```

then rebuild the frontend with `--build-arg VITE_API_URL=http://65.1.234.78/api`, copy it, and set
`CORS_ORIGINS=http://65.1.234.78` in `.env` (rebuild the backend). Browsers that saw the five-minute
HSTS header forget it after five minutes.

**Raising HSTS.** After a clean week, change `max-age=300` to `max-age=15552000` in
`deploy/nginx/nestaprime.conf` (the repository test pins the form), reinstall through the `sed` line in
step 5, `nginx -t`, reload.

**Web-server hardening (Amendment 58, Section 61).** `deploy/nginx/nestaprime.conf` also sends a
Content-Security-Policy and a Permissions-Policy, hides the nginx version, throttles the API (sign-in 10 a
minute, everything else 20 a second, per address, answering 429), closes `/api/docs` and `/api/redoc`, sets a
2 MB request limit with larger limits only on the upload routes, and stops a client choosing the address the
backend records. It is one configuration file: no rebuild, no migration. Install it the same way as any change
to the file, keeping the previous one:

```bash
cd /home/ubuntu/NestaPrime-Estimator && git pull
sudo cp /etc/nginx/sites-available/nestaprime /etc/nginx/sites-available/nestaprime.pre-hardening
sed "s/__DOMAIN__/your.domain.example/g" deploy/nginx/nestaprime.conf | sudo tee /etc/nginx/sites-available/nestaprime > /dev/null
sudo nginx -t && sudo systemctl reload nginx
```

Check from outside afterwards: the app and `/api/health` answer with `Content-Security-Policy` and
`Permissions-Policy` and a bare `Server: nginx`; `/api/docs` and `/api/redoc` answer 404 while
`/api/openapi.json` still answers 200; and a burst of wrong sign-ins from one address ends in 429. To go back,
copy `nestaprime.pre-hardening` over `nestaprime`, `nginx -t`, reload. If a screen breaks after the change,
open the browser console: a line beginning "Refused to ..." names the Content-Security-Policy directive that
blocked it, and that directive is the one to adjust. The office shares one public address, so if a real
morning rush ever meets a 429, raise the two `rate=` values (or the `burst=` on the API line) in that file.

**If the certificate cannot renew** (an expiry warning in the browser is the symptom): `sudo certbot
renew` shows why -- almost always port 80 blocked, the DNS record gone, or the `/var/www/certbot`
webroot missing. The HTTP server block must keep serving `/.well-known/acme-challenge/`.

## Backups & restore drill (Note R2)

*"A backup never restored is a hope, not a backup."* The AWS-side Lightsail snapshot
(already configured, covers the whole instance disk) doesn't know to quiesce Postgres
first -- a snapshot taken mid-write is not the same guarantee as a real `pg_dump`. This
closes that gap with a nightly consistent dump that lands *inside* the same instance
disk the Lightsail snapshot already covers, so it needs no new off-instance storage or
AWS credentials.

**One-time setup, on the server:**

```bash
chmod +x deploy/backup_db.sh deploy/restore_drill.sh
crontab -e
```

Add a line that runs the dump every night before Lightsail's own snapshot window (check
the instance's actual snapshot schedule in the Lightsail console and pick a time a
couple of hours ahead of it):

```cron
0 2 * * * /home/ubuntu/NestaPrime-Estimator/deploy/backup_db.sh >> /home/ubuntu/nestaprime-backups/backup.log 2>&1
```

Dumps land in `~/nestaprime-backups/` as `nestaprime_estimator_<UTC timestamp>.sql.gz`,
gzip-integrity-checked before it ever overwrites anything, with the newest 14 kept and
older ones pruned automatically (`deploy/backup_db.sh [dir] [retention_count]` to
override either).

**Quarterly restore drill.** Two halves -- both need to pass to actually trust the
backup, not just one:

1. **The pg_dump half (do this one every quarter, no Lightsail console needed):**
   ```bash
   deploy/restore_drill.sh ~/nestaprime-backups/nestaprime_estimator_<latest>.sql.gz
   ```
   Spins up a throwaway, fully isolated `postgres:16` container (never touches the
   real database), restores the dump into it, prints every table's row count, and
   exits non-zero if `users`/`sports` come back empty -- a restore that "succeeds" but
   recovers nothing is exactly the failure mode this drill exists to catch. Tears the
   container down automatically either way.
2. **The full instance-snapshot half (do this one too, at least annually, since it
   exercises the part `restore_drill.sh` can't -- an actual new Lightsail instance):**
   In the Lightsail console, restore the latest automatic snapshot to a **new** test
   instance (never overwrite the live one). On that test instance: `docker compose -f
   docker-compose.prod.yml up -d`, confirm `curl http://127.0.0.1:8000/health` answers,
   log into the app with a real account, open an existing project, confirm its data is
   there. Delete the test instance once confirmed (Lightsail bills for a running
   instance).

Record every drill -- pass or fail -- in [docs/ops/restore-drill-log.md](../docs/ops/restore-drill-log.md), the same "recurring, provably done" discipline Note R2 itself asks for.

## What's deliberately not here yet

- **HTTPS** -- serving plain HTTP on the IP directly; no domain name to get a TLS cert
  against yet. Worth revisiting once there's a domain pointed at this IP (`certbot
  --nginx` is the usual path).
- **A process supervisor restarting the stack on server reboot** -- `restart:
  unless-stopped` in the compose file brings containers back after a Docker daemon
  restart, but nothing currently re-runs `docker compose up` after a full server reboot
  automatically (a systemd unit or `docker compose` running via `crontab -e` with
  `@reboot` would close this).
