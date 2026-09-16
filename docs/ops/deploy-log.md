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

**Correction (16 September 2026):** this entry was wrong -- `git status` on
2026-09-16 found production's checkout still sitting at `56789d4` (PR #54, one
commit *before* PR #55 even), meaning `git pull` either wasn't actually run
during this deploy or ran in the wrong directory/session. The build/smoke-test
steps above ran against stale code despite reporting success; the health check
and frontend-200 checks pass regardless of which commit is deployed, so they
didn't catch it. Amendment 12 did not actually reach production until the
2026-09-16 entry below, which pulled it in along with Amendment 13. Lesson:
smoke tests need to check *which commit* is live (e.g. a `/health` response
carrying a git SHA, or `git rev-parse HEAD` on the server checked against the
merge commit), not just that the server responds.

---

## 2026-09-16 -- PRs #55-#63: Amendment 12 (dashboard/nav) + Amendment 13 (AI-assisted content), all in one deploy

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `56789d4` -> `748d627`

Production's checkout was found still on `56789d4` (see the correction above) --
this deploy is really "catch production up to `main`", which happens to bring
two amendments' worth of work at once: Amendment 12 (dashboard drill-down/nav
restructure, PR #57) and all four parts of Amendment 13 (AI-assisted content:
shared `ai_content.py` service #59, Quotation `cover_note` #60, message drafts
#61, report summaries #62), plus the deploy-log/register bookkeeping PRs
(#55, #58, #63).

**One new Alembic migration** (`5f6c4a6134d6 -> ecaaa65ec8d4`, adds
`quotations.cover_note`) -- confirms the database itself was already current
with Amendment 11's migration despite the code checkout lagging, i.e. the
DB and the git checkout had drifted independently. Applied cleanly, both
gunicorn workers started without error.

Confirmed before deploying that `ANTHROPIC_API_KEY` is unset on the server's
`.env` (Decision A from `docs/annexures/Section-12-specs.md` -- a Director-
supplied key is still pending) -- every "Draft with AI" / "Generate summary"
button added by Amendment 13 reports "AI drafting is not configured" rather
than hanging or erroring, same graceful-degradation discipline as
WhatsApp/Telegram's own unset keys.

**Smoke test:** `/health` -> `{"status":"ok"}` (200). Frontend root -> 200.

---

## 2026-09-16 -- Decision A resolved: ANTHROPIC_API_KEY configured on production

**Run by:** R. Patni (with AI development assistance)
**Not a code deploy** -- Director supplied the Anthropic API key; this closes
out `docs/annexures/Section-12-specs.md`'s Decision A, the one item blocking
Amendment 13 from actually working (as opposed to gracefully declining).

**First attempt corrupted the key**: `echo '...' >> backend/.env` wrote the
literal Unicode bullet character (U+2022) in place of the key -- whatever
displayed/relayed the command to the terminal had auto-masked the
secret-looking string, and the masked *display* is what got typed, not the
real value. Confirmed via `cat -A backend/.env`, which showed `M-bM-^@M-"`
(bullet's UTF-8 bytes) repeated in place of the key. First `generate_text`
call failed with `UnicodeEncodeError` building the `x-api-key` header, not
`AiContentError` -- a genuinely different failure mode than "not configured",
worth recognizing next time.

**Fix:** removed the bad line (`sed -i '/^ANTHROPIC_API_KEY=/d' backend/.env`),
then wrote the key via an interactive `read -r -p` prompt instead of a
copy-pasted command -- typed/pasted directly into the live SSH session rather
than through any rendering layer that could mask it. Verified ASCII-clean
with `grep ... | grep -qP '^[\x00-\x7F]+$'` before rebuilding, deliberately
without re-printing the key.

**Verification:** rebuilt the backend, then ran `ai_content.generate_text(...)`
directly inside the production container -- `SUCCESS: hello`, a real Claude
response. Amendment 13's three AI-content surfaces (Quotation cover note,
message drafts, report summaries) are now fully live, not just gracefully
declining.

**Lesson for future secret entry:** never hand a secret to a user through a
copy-pasted command block if the display/relay path might mask it -- use an
interactive prompt (`read -r -p`, or an editor) so the value goes straight
from the user's own paste into the shell, with no rendering step in between
that could substitute a masked display string for the real bytes.

---

## 2026-09-16 -- pinned Reports shortcut on the Dashboard

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `748d627` -> `c496625`
**Frontend-only** -- no backend rebuild, no migrations.

Director asked to pin the Reports screen for quick access -- adds a small
"📌 Reports" button next to "+ New project" on the Dashboard, jumping
straight to Reports without opening the Reports nav dropdown.

**Smoke test:** frontend root -> 200.
