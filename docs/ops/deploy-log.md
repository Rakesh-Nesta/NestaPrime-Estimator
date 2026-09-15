# Deploy Log

Record of what actually shipped to the Lightsail production server
(`65.1.234.78`), separate from [`docs/ops/restore-drill-log.md`](restore-drill-log.md)
which is scoped specifically to Note R2's quarterly backup/restore drills. See
[`deploy/README.md`](../../deploy/README.md) for the deploy procedure itself.

Every entry: date, who ran it, what commit range/PRs shipped, and the smoke-test
result. A deploy that wasn't smoke-tested is a deploy nobody's confirmed actually
works -- same discipline as the restore drill log.

---

## 2026-09-15 -- 16 commits / 8 PRs (#38-#53): cross-sell, WhatsApp/Telegram, backup infra, field settings, All Quotations, Amendment 11

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `c08e300` -> `7272afe`

Backend rebuilt (4 pending Alembic migrations applied automatically on container
start: cross-sell addon catalog, Telegram channel/provider IDs, field_settings
table, `rate_items.rate` nullable) and frontend rebuilt. Confirmed before
deploying that `WA_GATEWAY_BASE_URL` / `WA_GATEWAY_API_KEY` /
`WA_GATEWAY_WEBHOOK_SECRET` / `TELEGRAM_BOT_TOKEN` are all unset on the server's
`.env` -- WhatsApp/Telegram sending stays disabled (fast FAILED status, not a
hang) until someone deliberately configures them; not a blocker for this deploy.

**Smoke test:** `/api/health` -> `{"status":"ok"}` (200). Frontend root -> 200.
New JS bundle -> 200. Backend startup logs showed all 4 migrations apply
cleanly and both gunicorn workers start without error.

---

## 2026-09-15 -- PR #54: hide Master Settings, Sports & Scope Admin, and Rate Sheet from Sales

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `7272afe` -> `56789d4`
**Frontend-only** -- no backend rebuild, no migrations.

Fixes three nav items that were visible to the Sales role but led to dead ends
(silent or loud 403s on the underlying data) -- see PR #54 for the full
before/after verification against a real Sales-role account locally.

**Smoke test:** `/api/health` -> `{"status":"ok"}` (200). Frontend root -> 200.
`index.html` confirmed pointing at the newly built `index-D54Up4bP.js` /
`index-CiUx9lcb.css`, and that exact bundle served 200 directly. Not
re-verified against a real Sales account *on production* (deliberately --
creating a throwaway account there would leave visible clutter in real
dashboard/report data); the deployed bundle is byte-identical to the one
already verified locally as a real Sales-role account before merging PR #54.

---

## 2026-09-15 -- seed data fix: Amendment 11's rate card was never seeded on production

**Run by:** R. Patni (with AI development assistance)
**Not a code deploy** -- found while running Note R2's restore drill against real
production data for the first time (see `restore-drill-log.md`'s second 2026-09-15
entry). The earlier deploy's database *migration* (`rate_items.rate` nullable) had
gone out correctly, but its two one-off seed scripts never had -- production still
had the pre-Amendment-11 rate card (9 labour categories, 20 rate items) despite the
schema supporting the new ones.

**Fix:** ran both scripts directly against the production backend container:
```
docker compose -f docker-compose.prod.yml exec -T -e PYTHONPATH=/app backend python scripts/seed_labour_categories.py
docker compose -f docker-compose.prod.yml exec -T -e PYTHONPATH=/app backend python scripts/seed_rate_items.py
```
Both are re-run-safe (skip anything that already exists by key/natural key), so this
carries the same no-risk profile as the migrations themselves.

**Verification:** `SELECT count(*) FROM labour_categories` -> 10 (was 9),
`SELECT count(*) FROM rate_items` -> 23 (was 20) -- both now match local dev exactly.

**Lesson for future deploys:** `deploy/README.md`'s "Redeploying after a code change"
section doesn't mention one-off seed scripts at all -- worth remembering that a new
Alembic migration landing cleanly says nothing about whether a PR that also added
seed data actually got that data onto production. Every future PR that adds a
`scripts/seed_*.py` call should have that call added to the deploy checklist, not left
to be caught by the next quarterly drill.

---

## 2026-09-15 -- PR #57: Amendment 12, dashboard drill-down & nav restructure

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `00c4379` -> `b93a153`
**No Alembic migrations** -- Amendment 12 added only new API routes/read
endpoints (`GET /projects`, `GET /estimates`, `status_group` on `GET
/quotations`) and frontend screens/nav, no schema changes.

Backend rebuilt (`docker compose -f docker-compose.prod.yml up -d --build
backend`) and frontend rebuilt/exported with `VITE_API_URL=http://65.1.234.78/api`,
copied into `/var/www/nestaprime/dist/`.

**Smoke test:** `/health` -> `{"status":"ok"}` (200). Frontend root -> 200.
