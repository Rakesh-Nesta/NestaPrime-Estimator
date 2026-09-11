FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

# Migrations run on every container start, not just first deploy -- safe
# because Alembic upgrades are idempotent (upgrade head on an already-
# current DB is a no-op). Two workers: this targets the 2GB Lightsail
# instance from deploy/README.md, not a high-traffic deployment.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app --workers 2 --worker-class uvicorn_worker.UvicornWorker --bind 0.0.0.0:8000 --timeout 60"]
