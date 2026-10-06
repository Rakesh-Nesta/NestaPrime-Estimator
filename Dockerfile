FROM python:3.12-slim

WORKDIR /app

# Only the lightweight client runs here. The signature database and scanning
# engine live in the separately bounded clamd container, reached over a Unix socket.
RUN apt-get update \
    && apt-get install -y --no-install-recommends clamdscan \
    && rm -rf /var/lib/apt/lists/*

# pip first, pinned: the python:3.12-slim base bundles pip 25.0.1, which carries six advisories (PYSEC-2026-196, -1795, -1796,
# -2875, -2876, -3721; CVE-2026-8643, -1703, -3219, -6357, -13346 and CVE-2025-8869). All are fixed in pip >= 26.2.0; 26.2.1 (2026-08-04)
# is the newest release and only fixes a keyring regression on top of 26.2. Installed BEFORE any application dependency so that
# every later install is done by the fixed pip, and so the image's own installer is not an unaudited exception.
RUN pip install --no-cache-dir "pip==26.2.1"

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

# Migrations run on every container start, not just first deploy -- safe
# because Alembic upgrades are idempotent (upgrade head on an already-
# current DB is a no-op). Two workers: this targets the 2GB Lightsail
# instance from deploy/README.md, not a high-traffic deployment.
# --forwarded-allow-ips: Amendment 55 (Section 59). nginx sends X-Forwarded-Proto, but this container
# sees nginx through the Docker bridge, not 127.0.0.1, so by default the header is ignored and any
# redirect the app builds names http:// -- blocked as mixed content once the page is HTTPS. Safe to
# trust everywhere: the port is published on the host's loopback only (docker-compose.prod.yml), so
# nginx is the only client.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app --workers 2 --worker-class uvicorn_worker.UvicornWorker --bind 0.0.0.0:8000 --timeout 60 --forwarded-allow-ips='*'"]
