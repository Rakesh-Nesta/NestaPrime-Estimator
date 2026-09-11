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
all 19 are now closed, including small-job fast-track (M.2 rule 8), Procurement-safe Consumption
Sheet/BOM exports (K.3), and Director-editable flooring/lighting catalogues.

That last one is narrower than its one-line audit description implied, worth stating plainly
rather than repeating the headline claim: of the five catalogues the audit named, two
(netting grades, accessory catalog) turned out to already be Director-editable tables from an
earlier gap, and the structural steel/pipe specs (`STRUCTURE_DEFAULTS`, `PIPE_WEIGHT_KG_PER_M`)
were deliberately left as hardcoded Python dicts — they're IS 1239 engineering standards, not
business figures a Director tunes, a distinction the codebase's own code comments already argued
before this gap was picked up. Only the flooring guide and lighting lux/pole-count tables were
actually built.

See [`docs/audit-closure.md`](docs/audit-closure.md) for the full gap-by-gap closure record,
including this one and two other judgment calls (a blueprint contradiction on Tender Mode's GST
toggle, and how granular the Tender BOQ actually needed to be).

Since then, from the blueprint's own Phase 1b roadmap (P.2): Excel rate import for the Rate
Sheet and a mobile-responsive site-survey form are both built. Rate verification turned out to
already exist (the AI/Manual confirm flow, J.1) — not actually a gap. 3-project calibration
(±10% actuals-vs-estimate validation) is not done and can't be until real completed-project cost
data exists to validate against; it isn't something this codebase can fabricate.

Two further gaps outside both the 19 ranked items and the Phase 1b roadmap were raised directly
and closed: Director-only user management (create, deactivate/reactivate, change role, reset
password — a screen where before an account could only be created via a raw DB script), with a
backend-enforced forced-password-change gate on any account just created or reset; and a
mobile-responsive rewrite of the app's global navigation header, found incidentally while
verifying the site-survey form above.

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
