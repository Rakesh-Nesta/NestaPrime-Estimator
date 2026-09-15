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
