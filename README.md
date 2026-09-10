# NestaPrime Estimator

[![Backend CI](https://github.com/Rakesh-Nesta/NestaPrime-Estimator/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Rakesh-Nesta/NestaPrime-Estimator/actions/workflows/backend-ci.yml)

Pre-sales quotation and lead-tracking tool for NestaPrime Sports Infrastructure. Built from the
project's own blueprint (see `docs/` — hand it the `NPS_FINAL_...` package from the design phase).

## Status

Phase 1a foundation, in progress. Built so far: Postgres schema (users, 6 fixed roles), JWT auth
with server-side role gating, a login screen. Not yet built: Project Setup, the sport/estimation
engine, the Cost Sheet → Estimate → Quotation chain — see the blueprint's own Phase 1a scope
(Part P.2) for what's next.

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL 15
- Frontend: React, Vite, Tailwind CSS
- Auth: JWT (argon2 password hashing), 6 fixed roles (sales, pm, director, procurement,
  site_engineer, ca_tax)
- Local dev database: PostgreSQL via Docker Compose

## Running locally

### 1. Database

```
docker compose up -d
```

Waits for a healthy Postgres on `localhost:5432` (see `docker-compose.yml` for credentials — dev
only, not for anything real).

### 2. Backend

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# edit .env: SECRET_KEY should be a real random value before anything but local dev
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python scripts\seed_test_user.py   # creates director@nestaprime.local / ChangeMe!1
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`, sign in with the seeded test user.

### 4. Tests

```
cd backend
.venv\Scripts\python -m pytest tests/ -v
```

Tests run against a separate `nestaprime_estimator_test` database on the same Postgres container
(create it once: `docker exec <container> psql -U nestaprime -d nestaprime_estimator -c "CREATE DATABASE nestaprime_estimator_test;"`).
