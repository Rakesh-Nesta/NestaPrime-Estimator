# NestaPrime Estimator

[![Backend CI](https://github.com/Rakesh-Nesta/NestaPrime-Estimator/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Rakesh-Nesta/NestaPrime-Estimator/actions/workflows/backend-ci.yml)

Pre-sales quotation and lead-tracking tool for NestaPrime Sports Infrastructure. Built from the
project's own blueprint (see `docs/` — hand it the `NPS_FINAL_...` package from the design phase).

## Status

Built and tested: the full Cost Sheet → Estimate → Quotation document chain (draft, revise,
verify, approve, release, send, won/lost) with role-based cost/margin visibility (K.3), the
sport/estimation take-off engine (structures, flooring, base, drainage, lighting, specialty
modules, site prep), Tender Mode (BOQ export, GST inclusive/exclusive toggle, live L1 view,
EMD/BG/DLP/cess), the rate sheet with regional multipliers, message templates, client/vendor
consent tracking, a check-on-read jobs-runner pattern for expiry/SLA/reminder logic, and PDF/export
generation for every document type.

An internal completion audit ("Blueprint Ledger") tracked 19 ranked gaps against the blueprint;
16 are closed. Three remain open:

- **Small-job fast-track (M.2 rule 8):** Resurfacing/Repair jobs under a confirm-threshold
  skipping straight from Cost Sheet to Quotation under standing PM pre-approval — not yet built.
- **Procurement-safe Consumption Sheet / BOM exports:** Procurement is currently blocked from
  these exports entirely, rather than let in with cost/margin stripped (K.3's actual intent).
- **Director-editable technical catalogues:** flooring/structure/netting/fixture/equipment specs
  still live as Python dicts in the API layer; only their *rates* are Director-editable via Master
  Settings today, not the specs themselves.

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
.venv\Scripts\python scripts\seed_test_user.py   # Dev-only credentials -- never deploy as-is.
                                                  # Creates director@nestaprime.local / ChangeMe!1
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
