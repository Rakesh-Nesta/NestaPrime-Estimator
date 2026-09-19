# Deploy Log

Record of what actually shipped to the Lightsail production server
(`65.1.234.78`), separate from [`docs/ops/restore-drill-log.md`](restore-drill-log.md)
which is scoped specifically to Note R2's quarterly backup/restore drills. See
[`deploy/README.md`](../../deploy/README.md) for the deploy procedure itself.

Every entry: date, who ran it, what commit range/PRs shipped, and the smoke-test
result. A deploy that wasn't smoke-tested is a deploy nobody's confirmed actually
works -- same discipline as the restore drill log.

---

## 2026-09-19 -- PRs #121-#123: Amendments 22-23 (settings/override validation,
sequence-number race)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `ac3d056` -> `89f703a` (PR #121 was the register entries + both
approved specs, docs-only; #122 and #123 are the two independent implementation PRs,
each rebased onto `main` twice as the PRs before it merged -- both auto-merged/rebased
cleanly since they touch entirely unrelated files)
**Backend only** -- no new migration (neither amendment changed the schema).

Both amendments were self-identified during a third proactive gap audit against the
register, which this time deliberately targeted a bug class already proven real in this
codebase (the Amendment 18 timezone-comparison bug) -- that specific check came back
clean, but two new gaps were found instead. Amendment 22: neither a Master Setting nor a
document-scoped Override validated its value at write time, so a bad entry didn't fail
until a later document computation crashed with a bare, undiagnosable `ValueError`; fixed
via a shared `parse_setting_number` helper wrapping every numeric parse across five API
modules, a GST-divisor guard in `pricing.py`, and write-time rejection for Overrides
scoped to when the Setting they replace was itself numeric. Amendment 23:
`_generate_project_no`/`_po_number` computed the next sequence number with no row lock,
so two concurrent creations could compute the same number and the second commit
surfaced as an unhandled `IntegrityError`; fixed via a `create_with_retry` helper that
catches the collision and recomputes.

**Deploy went smoothly** -- backend-only rebuild and restart, logs confirmed clean
(`Application startup complete` on both workers, no errors, no migration line since none
was needed).

**Live-verified both amendments in production**, not just via the automated test suite
(120 tests total across both PRs, all passing in CI): reactivated
`verify-director@nestaprime.local` again. Amendment 22: posted a document-scoped
Override with a numeric `master_value` but a non-numeric `override_value` -- rejected
with a clear `422` naming the setting, while a genuinely numeric override on the same
setting still succeeded with `201`. Amendment 23: created two projects back to back,
confirming both succeeded with distinct, correctly sequential numbers (no crash, no
regression in the normal, non-colliding path). The GST-divisor guard itself was
deliberately **not** live-tested against the real, global `gst_rate_percent` Master
Setting -- doing so would have made every live pricing calculation see a broken rate for
the duration of the test, an unacceptable risk on a production system currently in real
use. That guard is covered instead by `backend/tests/test_override_validation.py`,
which exercises it against the real `/pricing/quote` endpoint in the isolated test
database and passed in CI before this deploy.

**Known leftover:** a third "Deploy Smoke Test Client (delete me)" / two projects from
the Amendment 23 check remain in production data, same reasoning as the previous two
deploys' leftovers (no client-delete endpoint by design).

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-19 -- PRs #116-#119: Amendments 19-21 (structure form crash, PO receiving,
double-submit guard)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `d317d48` -> `8af1dc7` (PR #116 was the three approved specs,
docs-only; #117, #118, #119 are the three independent implementation PRs, each rebased
onto `main` in turn as the ones before it merged -- #119 shares `CostSheetBuilder.jsx`
with #117 and auto-merged cleanly, verified directly before pushing)
**Backend + frontend** -- no new migration (Amendment 20 only added an optional Pydantic
field, no schema change).

All three amendments were self-identified during a second proactive gap audit against
the register: Amendment 19 fixes a real crash (`TypeError: Cannot read properties of
null`) in the Structure take-off form's "Use recommendation" button when the
recommended type doesn't parse; Amendment 20 replaces Purchase Order receiving's
unconditional overwrite with an optimistic-concurrency check (rejects a stale update
with `409` instead of silently discarding a concurrent receipt) and fixes a related bug
where `po.status` never reverted to `issued`; Amendment 21 adds a `saving`-state guard
to all 21 Cost Sheet take-off forms so a double-click can't duplicate a line.

**Deploy needed both a backend and frontend rebuild** this time (the previous 17-18
deploy was backend-only) -- `git pull`, `docker compose up -d --build backend`, then
the frontend export/copy sequence (`docker build --target export` -> `/var/www/
nestaprime/dist/`). Backend logs confirmed clean (`Application startup complete` on
both workers, no errors).

**Live-verified Amendment 20 end-to-end** in production via the same
`verify-director@nestaprime.local` pattern as the last deploy: raised and issued a real
PO, received 200 units (succeeded, status -> `partially_received`), then attempted a
second receipt still asserting the old `expected_received_qty=0` -- rejected with `409`,
and the first receipt's 200 units were confirmed intact afterward (not overwritten).
Correcting the line back to 0 with the correct `expected_received_qty=200` reverted
`po.status` to `issued` as designed. Amendments 19 and 21 are frontend-only guards
already verified via clean production build and no console errors on both the local dev
server and the live production frontend (`http://65.1.234.78`) after deploy -- their
exact trigger conditions (an unparseable recommendation; a double-click race) aren't
easily reproducible through normal seeded data, so they're verified by direct code
trace plus this regression check rather than a full interactive repro.

**Known leftover:** a second "Smoke Test Client 2 (delete me)" / project / cost sheet /
PO from the Amendment 20 check remains in production data, same reasoning as the
previous deploy's leftover (no client-delete endpoint by design).

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-19 -- PRs #111-#113: Amendments 17-18 (export sanitization, login lockout)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `c56c927` -> `7025bfa` (PR #111 was the register entry + both approved
specs, docs-only; #112 and #113 are the two independent implementation PRs, split per
this session's usual practice since they touch unrelated files)
**Backend only** -- one new Alembic migration (`b98a7f5bc39a`, adds
`failed_login_attempts`/`locked_until` to `users`, auto-applied on container start). No
frontend change, no new seed script.

Both amendments were self-identified during a Director-requested proactive audit of the
codebase against the register, rather than a Director-reported gap: Amendment 17 closes
a real CSV/XLSX formula-injection hole across every Excel/CSV export (a value starting
with `=`, `+`, `-`, or `@` now gets a leading apostrophe at export time, neutralizing it
as a spreadsheet formula without touching stored data or the app's own live formulas);
Amendment 18 adds a 5-attempt / 15-minute login lockout, persisted on the `User` row
(not in-memory, since production runs 2 gunicorn workers) -- unknown emails never count
toward any account's lockout, closing an email-guessing DoS angle.

**Deploy went smoothly** -- `git pull` and `docker compose up -d --build backend`, no
502 this time. Confirmed the migration actually applied (not just that it didn't error)
by querying the `users` table schema directly (`\d users`) and `SELECT version_num FROM
alembic_version` -- both new columns present, version at `b98a7f5bc39a`.

**Live-verified both amendments end-to-end inside the production container**, not just
via the migration/schema check: created (and reused the throwaway-verification-account
pattern for) `verify-director@nestaprime.local`, which turned out not to already exist
on production (a dev-only fixture until now) -- created it fresh, DIRECTOR role,
deactivated again afterward. Amendment 17: posted a real Cost Sheet line with
`category`/`item_name`/`spec` all crafted as formula-injection payloads
(`=HYPERLINK(...)`, `+SUM(1+1)`, `@evil`), exported it, and confirmed all three came
back prefixed with `'` in the real XLSX while the sheet's own live Amount formula
(`=F2*G2`) was untouched. Amendment 18: 5 deliberate failed logins against the same
account each returned 401, and critically a 6th attempt with the *correct* password
also returned 401 -- the account was genuinely locked, not just rejecting bad guesses.

**Known leftover:** a "Smoke Test Client (delete me)" / project / cost-sheet line from
the Amendment 17 check remains in production data -- this app has no client-delete
endpoint by design (audit-trailed rather than deletable), so it stays as a harmless,
clearly-labeled artifact unless the Director wants it handled another way.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-19 -- PRs #107-#109: Section 22, Amendment 5's two remaining gaps

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `a64e4b0` -> `f0eeb62` (PR #107 was the Section 22 spec approval,
docs-only; #108 and #109 are the two independent implementation PRs, shipped as
separate PRs per Director instruction -- "approve, but split into two")
**Backend + frontend** -- one new Alembic migration (`water_available` made nullable,
auto-applied on container start).

Closes Amendment 5's two remaining confirmed-real gaps: `water_available` joins
field-settings governance (Amendment 2's own named pair with `power_available`, the
Quick checkbox becomes a Select matching `power_available`'s exact existing pattern);
City/District is wired into the `SelectWithOther` "Others" rule (its old trailing
"Other" entry was fully inert -- selecting it submitted the literal string "Other" to
the backend). Both live-verified before either PR was opened: water_available's real
"None" option confirmed via the actual `POST /projects` payload; City's "Others…" text
input confirmed the same way with a typed city name.

**First deploy attempt looked like a failure but wasn't:** `curl .../health` returned
`502 Bad Gateway` immediately after the backend rebuild. Diagnosed properly rather than
re-running blindly or assuming the code was broken: `docker compose ps` showed the
container genuinely running with no restarts; backend logs showed a clean startup with
`Application startup complete` at `08:58:14`; the nginx error log showed the failed
request hit the backend at `08:58:11` -- three seconds *before* the workers finished
booting, a transient race between gunicorn's master accepting connections and the
workers actually being ready, not a crash. Re-running the health check after workers
had time to finish booting confirmed `{"status":"ok"}`. Full backend suite (1151
passed) had already confirmed the code itself was sound before this deploy even
started, which is what justified treating the 502 as a timing issue worth
re-checking rather than a real regression to roll back.

**Smoke test:** `curl http://65.1.234.78/api/health` -> `{"status":"ok"}` (second
attempt, after the startup-race window passed). Full git-pull/docker-build/
frontend-export transcript plus the diagnostic logs above reviewed before logging this
entry as confirmed.

---

## 2026-09-19 -- PR #105: Section 21, Quick mode routes through Sport Selection

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `5b331e0` -> `3aece69`
**Frontend-only** -- no backend rebuild, no migrations.

Closes Amendment 2's remaining gap (register verification earlier today confirmed it
was still real, unlike several other entries corrected this week). Root cause wasn't a
missing "Dimensions" form field on Project Setup -- dimension entry lives on Sport
Selection (`CourtSize`) for both Quick and Detailed mode; Detailed mode already routed
through that screen, Quick mode skipped straight to Scope. One-line fix:
`onQuickSetupComplete` now routes to `screen="sports"`, matching `onProjectCreated`'s
existing routing -- reuses the exact validated dimension-entry path rather than
building a second one. Also fixed `ProjectSetup.jsx`'s stale "(customizable once
Amendment 9 ships)" copy, referencing a future event that had already happened the same
day it was written.

Live-verified before this PR was opened: Quick setup now lands on Select Sports with
the picked sport already added, standard size shown, and a working "Customize size"
control revealing real L(ft)/W(ft) inputs -- identical to what Detailed mode already
provided.

**Smoke test:** `curl http://65.1.234.78/api/health` -> `{"status":"ok"}`. Full
git-pull/frontend-export transcript reviewed before logging this entry -- `git pull`
correctly showed `Updating 5b331e0..3aece69` with every expected file
(`Section-21-specs.md`, `App.jsx`, `ProjectSetup.jsx`), frontend export build completed
cleanly (737.73kB copied to `/var/www/nestaprime/dist/`).

---

## 2026-09-19 -- Decision 1 resolved: real SMTP credentials configured on
production

**Run by:** R. Patni (with AI development assistance)
**Not a code deploy** -- Director supplied real Google Workspace SMTP credentials for
`info@nestaprime.com`; this closes out `docs/annexures/Section-17-specs.md`'s Decision
1, the one item blocking Section 17 (Amendment 8's email gap) from actually working (as
opposed to gracefully failing fast).

**First attempt failed:** `535 Username and Password not accepted` from Google, right
after generating a fresh app password. Checked the Workspace Admin Console's 2-Step
Verification settings first (Security -> Authentication -> 2-Step Verification) for an
org-level app-password restriction -- found nothing blocking, and 2-Step Verification
being genuinely on for the account (confirmed by the Google Account page allowing app
password creation at all) ruled out the enforcement setting as the cause. Diagnosed as
a copy-paste issue with the app password itself instead.

**Fix:** deleted the first app password, generated a fresh one, and re-entered it into
`backend/.env` via the same interactive-prompt pattern used for the Anthropic key (never
pasted through a channel that could mask or corrupt it) -- this time with an added
length check (`${#SMTP_PASS_VAL}` characters, confirmed 16) printed to the terminal
without ever printing the value itself, to catch a truncated/corrupted paste before
wasting another round trip. Backend rebuilt; `535` cleared immediately.

**Verification:** ran `email_gateway.send_email(...)` directly inside the production
container, targeting `info@nestaprime.com` itself -- `SUCCESS: email sent`, then
confirmed in the actual Gmail inbox (not just the SMTP handshake): landed in Inbox, not
spam, correct sender/subject/body. Amendment 8 is now fully closed end to end -- email
joins WhatsApp and Telegram as a genuinely live send channel, not just correctly-coded-
but-unconfigured.

**Lesson reinforced:** the same lesson from the 2026-09-16 Anthropic key incident held
here too -- always use an interactive prompt for secret entry, never a copy-pasted
command block. The length-check addition this time caught nothing (the first failure
was a genuine bad credential, not a display-masking corruption), but it's cheap
insurance worth keeping in the pattern going forward.

---

## 2026-09-18 -- PRs #98-#99: Amendment 10 correction, Section 20 (handbook
currency pass)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `0c4558c` -> `e3d9845` (PR #98 was the Section 20 spec approval plus
a correction to Amendment 10's stale register entry, docs-only; #99 is the actual
content)
**Frontend-only** -- no backend rebuild, no migrations.

**A real error in this session's own work, caught and corrected before it cost
anything:** the session initially described the handbook as its "largest gap" on the
roadmap, based on Amendment 10's own register text. Re-verifying against the actual
`frontend/src/handbookData.js` found a prior v3 pass (16 September) had already closed
most of it -- All Quotations, Vendors Admin, Price Requests, Cross-Sell Admin, and
Hindi/Hinglish terms were all already present; the register was simply never updated to
say so. Corrected the register first, then scoped and shipped the real remaining gap:
a new Education chapter (Amendment 15's Chat assistant, Amendment 16's Sport Build
Guide including Section 18's Construction Sequence -- never documented at all) and
three stale passages left over from before Sections 17 and 19 shipped (Documents
claimed email "delivers nothing"; Clients and FAQ Q18 both claimed the per-client
project list was missing). Two small related items folded in: Sports & Scope Admin's
field list now names the Construction Sequence tab, and both Help.jsx version labels
bumped 3->4. Direct content authorship, no AI-draft step, per the approved spec.

**Smoke test:** `curl http://65.1.234.78/api/health` -> `{"status":"ok"}`. Full
git-pull/docker-build/frontend-export transcript reviewed before logging this entry --
`git pull` correctly showed `Updating 0c4558c..e3d9845` with every expected file
(`handbookData.js`, `Help.jsx`, both spec docs), frontend export build completed
cleanly (737.74kB copied to `/var/www/nestaprime/dist/`).

---

## 2026-09-18 -- PRs #94-#96: deploy-log bookkeeping, Amendment 4 verification,
Section 19 (per-client project list)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `315d4c6` -> `0c4558c` (PR #94 was docs-only bookkeeping with no
server impact; #95 was the Section 19 spec approval plus an Amendment 4 register
verification, also docs-only; #96 is the actual code)
**Backend + frontend** -- no migrations.

Closes the one item from Amendment 4's 12 September findings that Amendment 12's
nav/dashboard restructure never touched: re-checking all five findings against current
code (not the register's own older text) confirmed four were already fixed as a side
effect of that restructure, and one remained genuinely open -- the Clients screen had
no per-client project list. `GET /projects` gained an additive `client_id` filter (same
role gate, combines with the existing `search`/`status` filters); `ClientsAdmin.jsx`
gained a collapsed-by-default "Projects" expand per client row, reusing
`AllProjects.jsx`'s own row shape rather than redesigning it. Pure data-wiring, no new
tables -- `Project.client_id` already existed and already drove real Cost Sheets. 3 new
backend tests (client_id scoping, combining with status, empty-list for a client with
no projects yet).

**One test-DB contamination incident caught and handled correctly during this work:**
running the new test file directly collided with a concurrent full-suite run already
using the same test database, producing 5 unrelated `test_users.py` failures
("relation does not exist") in that full-suite run. Diagnosed as contamination, not a
regression, by re-running the affected files in isolation (25/25 passed) once nothing
else was using the database, then re-running the full suite cleanly with no concurrent
runs -- exactly the discipline this project has followed since an earlier session first
hit this failure mode.

**Smoke test:** `curl http://65.1.234.78/api/health` -> `{"status":"ok"}`. Full
git-pull/docker-build/frontend-export transcript reviewed before logging this entry --
`git pull` correctly showed `Updating 315d4c6..0c4558c` with every expected file
(`projects.py`, `test_projects_list.py`, `App.jsx`, `ClientsAdmin.jsx`, `api.js`),
backend container built and started (`Healthy`/`Started`), frontend export build
completed cleanly (735.10kB copied to `/var/www/nestaprime/dist/`).

---

## 2026-09-18 -- PRs #90-#93: deploy-log/register bookkeeping, Section 18
(construction sequence)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `7dc946e` -> `315d4c6` (one deploy caught up four merges at once --
PRs #90 and #91 were docs-only bookkeeping with no server impact, #92 was the Section
18 spec approval, also docs-only; #93 is the actual code)
**Backend + frontend** -- one new Alembic migration (`construction_sequence_steps`,
auto-applied on container start).

The real reason for this deploy: PR #93, closing Amendment 16 Part 2 -- the
construction-sequence content the Section 16 spec explicitly deferred as genuinely new
content rather than something assembled from existing data. New
`ConstructionSequenceStep` table (one row per sport x fixed phase: site prep, sub-base,
flooring, structure/fixtures, lighting, accessories/finishing), authored through the
same AI-draft-then-Director-review pattern Amendment 13 established for Cover Notes and
client messages -- drafting never persists, only an explicit Director save does. Sports
& Scope Admin gained a "Construction sequence" tab; the Build Guide screen gained a
Construction Sequence section with a standing safety disclaimer; the Education chat's
grounding extends automatically through the existing client-side `sportContext` string,
no backend change needed for that part. 14 new backend tests; full backend suite run
locally alongside CI, both clean.

Live-verified with a real Anthropic call before this PR was even opened: drafted
badminton's six-phase sequence grounded in its actual dimensions/flooring/package data,
saved it, confirmed it rendered correctly on the Build Guide in fixed phase order with
the disclaimer, and confirmed the Education chat's own answer to a live question stayed
consistent with the saved sequence, disclaimer included.

**First smoke-test attempt's curl output wasn't visible in the terminal screenshot
provided** -- asked for confirmation rather than assume success, per the standing
discipline that an unconfirmed smoke test isn't a deploy. Second paste confirmed it.

**Smoke test:** `curl http://65.1.234.78/api/health` -> `{"status":"ok"}`. Full
git-pull/docker-build/frontend-export transcript reviewed before logging this entry --
`git pull` correctly showed `Updating 7dc946e..315d4c6` with every expected file
(`construction_sequence_step.py`, `construction_sequence.py`, the migration, the three
frontend files), backend container built and started (`Healthy`/`Started`), frontend
export build completed cleanly (733.49kB copied to `/var/www/nestaprime/dist/`).

---

## 2026-09-18 -- PR #89: Section 17, real email sending via SMTP

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `ee69919` -> `7dc946e`
**Backend + frontend** -- no migrations.

Closes the Email gap named in Amendment 8 (spec: PR #88, `docs/annexures/Section-17-specs.md`):
WhatsApp and Telegram already sent real messages via their own providers; Email only ever
logged a manual "recorded" status. New `backend/app/services/email_gateway.py` is a thin SMTP
client matching the exact `wa_gateway.py`/`telegram.py` pattern -- blank `SMTP_*` config fails
fast, a send failure sets `Message.status = failed` immediately, no retries/queueing. Live
browser verification (SMTP still unconfigured, as expected -- real credentials are the
Director's to supply later, same two-step flow as the Anthropic key) surfaced a real frontend
gap missed in the initial implementation: `MessagesPanel.jsx` still hard-coded email as a
provider-less, log-only channel, so the banner claimed email "does not actually send anything"
(now false) and the "Attach PDF" checkbox was hidden for email even though the backend supports
`include_document` uniformly across all three channels. Fixed in the same PR before merge.
Full backend suite: 1132 passed. HawkScan DAST was not run against this change -- no
`HAWK_API_KEY` and no interactive browser session available in this environment; reviewed the
new SMTP code manually instead (`smtplib`/`MIMEText` handle header encoding, no raw
string-concatenation into headers from user-controlled subject/recipient, so no obvious
SMTP header-injection path).

**First deploy attempt failed silently** -- commands were run from `~` instead of
`~/NestaPrime-Estimator`, so `git pull`, the backend rebuild, and the frontend build all
errored ("not a git repository", config/path not found), yet the smoke-test curl still
returned `{"status":"ok"}` because the *previous* deploy's containers were still running.
Caught before logging anything, per the standing discipline of requiring the full
git-pull/docker-build transcript, not just the curl result. Second attempt, run from the
correct directory, showed the real fast-forward (`ee69919..7dc946e`, all expected files
including `email_gateway.py` and `MessagesPanel.jsx`), a clean backend rebuild and container
restart, and a clean frontend export build (728.42kB copied to `/var/www/nestaprime/dist/`).

**Smoke test:** `curl http://65.1.234.78/api/health` -> `{"status":"ok"}`. Full git
pull/docker build/frontend export transcript reviewed before logging this entry.

---

## 2026-09-18 -- PRs #84-#86: deploy-log correction, Section 16 spec + approval,
Sport Build Guide

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `d89323e` -> `ee69919` (confirmed matching -- production's own
`git pull` started exactly at `d89323e`, the commit the previous deploy correctly left
it at, closing the loop on that earlier correction)
**Frontend-only** -- no backend rebuild, no migrations.

The actual reason for this deploy: PR #86, Section 16's Sport Build Guide. Director's
own new-hire scenario (a Sales person clueless on what a basketball court needs)
surfaced the gap live-testing the Education chat. `SportBuildGuide.jsx` assembles the
real, already-verified per-sport accessory/flooring/package-tier data that already
drives real Cost Sheets -- no new content authored, no new backend endpoints. Confirmed
live: `basketball_indoor`/`basketball_outdoor` are genuinely separate catalog entries,
and a follow-up chat question about flooring gave an answer that exactly matched the
Build Guide's own data for that sport. Also carries forward PR #84 (deploy-log
correction) and PR #85 (Section 16 spec + approval, docs-only) -- neither changes the
running app.

**Smoke test:** `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/` -> `200`.
Full git pull/docker build transcript reviewed before logging this entry, not just the
smoke-test line -- per the lesson recorded in the correction above.

---

## 2026-09-18 -- PRs #79-#83: register/handbook cleanup, Section 15 spec + approval,
Education tab AI assistant

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `d3bb3f5` -> `d89323e`
**Backend + frontend** -- no migrations.

**Corrects the entry below** (see its own correction note): today's `git pull` on
production showed `Updating d3bb3f5..d89323e` -- `d3bb3f5` is PR #78's own merge commit,
proving production had been sitting there since the 2026-09-17 deploy and had never
actually received PRs #79-#82 at all. This single pull caught all of it up at once,
alongside the real reason for today's deploy -- PR #83, the Education tab AI assistant
(Section 15): a new `POST /education/ask` endpoint (open to every role, grounded only in
the handbook content the frontend sends, no live app data ever reaches the model) and
`Education.jsx` becoming a real chat panel. Full backend suite: 1129 passed (9 transient
Postgres-not-yet-ready errors at the very start of one local run, confirmed clean
rerunning in isolation -- not a regression); CI green.

**Smoke test:** `curl -s http://127.0.0.1:8000/health` -> `{"status":"ok"}`; frontend
root -> `200`. Backend container built and started cleanly.

---

## 2026-09-18 -- PR #80: register/handbook cleanup + Section 15 registration

**Corrected 2026-09-18 -- this deploy never actually reached production.** The entry
below was written after the smoke test returned `200`, but that was a bare `curl`
against whatever the server already had running -- a stale, undeployed server also
returns `200` for `/`, so it wasn't real confirmation. No `git pull`/`docker build`
transcript was ever shown for this one, unlike every other entry in this log. The actual
deploy happened today, bundled into the entry directly above. Left here, corrected
rather than deleted, for the same reason the very first entry in this log's history was
corrected rather than silently rewritten -- the record should show the mistake, not hide
it. **Lesson**: a bare `200` isn't a deploy confirmation on its own; the git pull/docker
build transcript has to be seen too, same as every other entry in this log already
required.

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `5b09315` -> `dd285e5`
**Frontend-only** -- no backend rebuild, no migrations.

Docs-only register/handbook fixes bundled with one real frontend content change:
`handbookData.js`'s Master Settings entry now mentions the two Section 14 panels
(Company Details, Quotation terms & warranty), closing a gap found during a session
review. Also adds Annexure-2.md's missing "Implemented" note for Amendment 14, and
registers Amendment 15 (Education tab AI assistant) with its draft spec -- neither of
those two changes affect the running app.

**Smoke test:** `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/` -> `200`
(not a real confirmation -- see correction note above).

---

## 2026-09-17 -- PR #78: customizable Quotation company details and T&C/warranty text

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `3fce868` -> `d3bb3f5` (also carried forward PR #76/#77's docs-only
commits not yet pulled on production until this deploy)
**Backend + frontend** -- one new Alembic migration (auto-applied on container start).

Section 14 (approved spec): a labeled Company Details panel in Master Settings over
data that already fed the Quotation PDF (legal name, PAN, GSTIN, bank details), plus a
genuinely new capability -- the 8 T&C clauses and 5-row warranty table, previously
hardcoded Python strings with no settings path, are now Director-editable with a live
preview before saving. Migration widens `settings.value` (200->text) and
`audit_log_entries.old_value`/`new_value` (500->text) -- both hit their old limits
against real T&C-length text during local verification, fixed before this shipped.
Full backend suite: 1122 passed locally before merge; CI green.

**Smoke test:** `curl -s http://127.0.0.1:8000/health` -> `{"status":"ok"}`; frontend
root -> 200. Backend container built and started cleanly (a failed migration would have
kept the container from starting at all).

---

## 2026-09-17 -- PR #75: embed Quotation photo attachments into the generated PDF

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `6f2effa` -> `f121866` (also carried forward PR #74's docs-only commit,
`dd26828` -> `6f2effa`, not yet pulled on production until this deploy)
**Backend-only** -- no frontend rebuild, no migrations.

The Quotation's existing Attachments panel let users attach images, but the generated
PDF never included them -- real quotations sent today carry a site layout diagram or 3D
render for client clarity, which the app's PDF had no way to show. Any non-superseded
photo-tagged attachment on a Quotation now renders under a "Reference Images" heading in
its PDF, scaled to fit; a corrupt/unreadable file is skipped rather than breaking
generation. Full backend suite: 1112 passed locally before merge (1 unrelated,
pre-existing test-DB contamination error, confirmed clean in isolation) and CI green.

**Smoke test:** `curl -s http://127.0.0.1:8000/health` -> `{"status":"ok"}`. Backend
container rebuilt and started cleanly, no migration step (expected, no schema change).

---

## 2026-09-16 -- PR #73: handbook v3 (Section 13, closes the Amendment 10 gap)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `3c00e24` -> `dd26828`
**Frontend-only** -- no backend rebuild, no migrations.

Annexure 2 v1.11's register reconciliation (PRs #70-#72) found the in-app handbook
hadn't been updated since PR #34 (13 Sept), despite Amendments 11-13 shipping seven
new/updated screens since. Section 13's approved spec closed that gap: 7 new Full
Handbook entries (All Projects, All Estimates, All Quotations, Vendors Admin, Price
Requests, Cross-Sell Admin, Sports & Scope Admin), updated Documents/Reports entries
(AI cover note, AI summary, Excel/PDF export), the register's own named Hindi terms
woven into Quick Start and the Estimator Guide, and a version bump to v3. Frontend
rebuilt and redeployed the same session.

**Smoke test:** `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/` -> `200`.
Handbook content itself was already verified in-browser (Director role, local dev)
before merge -- all 19 entries and both role guides render correctly.

---

## 2026-09-16 -- PR #68: replace raw JSON report view with Excel/PDF export

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `c496625` -> `a1ac9dd`

Director reviewed the Reports screen and asked that the raw JSON debug dump be
replaced with proper exportable files -- both Excel and PDF, not just one.
Backend and frontend both rebuilt: two new report endpoints
(`GET /reports/{id}/export` for `.xlsx`, `GET /reports/{id}/pdf`), each gated
identically to `GET /reports/{id}` (`VISIBLE_ROLES[report.report_type]`), and
`Reports.jsx` now offers "Download Excel"/"Download PDF" buttons instead of
the `<pre>{JSON.stringify(...)}</pre>` block. No schema changes -- no new
Alembic migration to apply.

**Smoke test:** `/health` -> `{"status":"ok"}`. Frontend root -> 200. Backend
startup logs showed both gunicorn workers starting cleanly with no migration
step (expected, since this PR carries no schema change).

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
