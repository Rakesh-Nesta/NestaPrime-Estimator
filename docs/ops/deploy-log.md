# Deploy Log

Record of what actually shipped to the Lightsail production server
(`65.1.234.78`), separate from [`docs/ops/restore-drill-log.md`](restore-drill-log.md)
which is scoped specifically to Note R2's quarterly backup/restore drills. See
[`deploy/README.md`](../../deploy/README.md) for the deploy procedure itself.

Every entry: date, who ran it, what commit range/PRs shipped, and the smoke-test
result. A deploy that wasn't smoke-tested is a deploy nobody's confirmed actually
works -- same discipline as the restore drill log.

---

## 2026-09-24 -- PRs #184 + #185: Amendment 49 (Quotations header)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `c555a3c` -> `12b0e68`
**Backend rebuild + frontend rebuild, no migration** (`quotations_admin.py`;
`AllQuotations.jsx`, `AllEstimates.jsx`, `Sidebar.jsx`, `Dashboard.jsx`, `App.jsx`). Both PRs
were merged before the first deploy, so they shipped together (the spec's proposed
Part-A-first deploy did not happen).

`git pull` fast-forwarded `c555a3c..12b0e68`; `docker compose -f docker-compose.prod.yml up -d
--build backend` rebuilt and restarted the backend (db healthy; logs show both workers booting
and "Application startup complete", no errors); frontend build clean and copied from
`/tmp/nestaprime-frontend/dist/*`; `/api/health` `{"status":"ok"}`. (The pasted `git log` line
failed with `fatal: '1?'` -- a stray carriage return in the pasted command -- but the pull's own
output shows the fast-forward to the merge commit.) Confirmed by the served bundle changing
(`index-B2931D9s.js` -> `index-BY1Qsrjh.js`) and by downloading it: it contains the new
Quotations screen text ("Every quotation and estimate across every project", "+ New project",
"From lead:", "Open in Opportunities", "Export CSV") and still contains the What's-next hints,
the Leads & Clients search and the phone layout. Production's OpenAPI lists `lead_name` and
`opportunity_id` on `QuotationSummaryOut` with `cost_total`/`margin_percent`/`below_floor`
nullable; anonymous `GET /quotations` and `GET /quotations/export` both return 401.

**Not verified in production:** a logged-in Quotations screen, and the Sales and PM roles (no
active production account for either); those were verified in real Chrome locally against the
identical code.

---

## 2026-09-24 -- PR #181: Amendment 40 (What's-next hints on the Cost Sheet, Estimate, Quotation stages)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `e535432` -> `c555a3c` (includes PR #179's docs-only close-out)
**Frontend-only** -- no migration, no backend rebuild (`Documents.jsx`).

`git pull` fast-forwarded `e535432..c555a3c`; frontend Docker build clean; copied from
`/tmp/nestaprime-frontend/dist/*`; `/api/health` `{"status":"ok"}`. Confirmed by the served
bundle changing (`index-B7lZRA0W.js` -> `index-B2931D9s.js`) and by downloading it: it contains
the "What's next:" label and the hint sentences (e.g. "Awaiting PM/Director to build the Cost
Sheet.", "Verified -- the Estimate is below.", "Client rejected this Estimate.", "Won -- Work
Order can be created."), and still contains the Leads & Clients search box and the phone layout.

**Not verified in production:** a logged-in Documents screen (no login was used for this
deploy); the hint wording has not yet had the Director's copy review the spec asks for.

---

## 2026-09-24 -- PR #178: Amendment 47 Part B (Leads & Clients tabs, search, collapsible add forms)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `8b71a35` -> `e535432`
**Frontend-only** -- no migration, no backend rebuild (`ClientsAdmin.jsx`, `App.jsx`).

`git pull` fast-forwarded `8b71a35..e535432`; frontend Docker build clean; `/api/health`
`{"status":"ok"}`. Confirmed by the served bundle changing (`index-ida_2CSV.js` ->
`index-B7lZRA0W.js`) and by downloading it: it contains the Leads & Clients search box, "+ Add
Enquiry", "Open in Opportunities", the no-match message, Edit details and the phone layout, and
no longer contains the old page's blurb.

**Not verified in production:** an authenticated click-through (no active Sales account; not
logged in as a Director for this deploy). The UI was exercised in real Chrome locally, 24/24
checks, against the identical code.

---

## 2026-09-24 -- PR #177: Amendment 47 Part A (edit a lead's or client's details)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `10a58f6` -> `8b71a35`
**Backend rebuild + frontend rebuild, no migration** (`clients.py`, `opportunities.py`,
`EditDetailsForm.jsx`, `Opportunities.jsx`, `ClientsAdmin.jsx`, `api.js`).

`git pull` fast-forwarded `10a58f6..8b71a35`; `docker compose -f docker-compose.prod.yml up -d
--build backend` rebuilt and restarted the backend container (db healthy); frontend build
clean; `/api/health` `{"status":"ok"}`. Confirmed by the served bundle changing
(`index-NczabCfy.js` -> `index-ida_2CSV.js`) and by production's OpenAPI now listing
`/clients/{client_id}/details` and `/opportunities/{opportunity_id}/details`; an unauthenticated
PATCH to each returns 401 while a nonexistent route returns 404, so the routes exist and are
auth-protected.

**Not verified in production:** an authenticated edit of a real record.

---

## 2026-09-24 -- PR #176: Amendment 47 Part C (phone layout)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `1ab5a89` -> `10a58f6` (includes the Amendment 47 registration and spec)
**Frontend-only** -- no migration, no backend rebuild (`App.jsx`, `Dashboard.jsx`,
`ClientsAdmin.jsx`, `FollowUps.jsx`, `Opportunities.jsx`).

**A first attempt did not deploy anything, and the pasted output alone would have hidden it.**
The git pull, Docker build, copy and `/api/health` all appeared to succeed, but the site still
served the old bundle (`index-DeWY-Pec.js`). Cause: `docker build --output /tmp/nestaprime-frontend`
produces `/tmp/nestaprime-frontend/dist/`, and the handed-over copy command used
`/tmp/nestaprime-frontend/*`, which copied the `dist` folder itself into
`/var/www/nestaprime/dist/dist/` instead of the files. Caught by downloading the served bundle
and finding the old root layout class in it. **Correct command:**
`sudo cp -r /tmp/nestaprime-frontend/dist/* /var/www/nestaprime/dist/`. A stray
`/var/www/nestaprime/dist/dist/` folder was left behind (harmless, nothing links to it); its
removal was suggested to the operator and is not confirmed. A second handed-over command block
also contained a stray markup fragment and failed to parse, so it changed nothing.

After the corrected copy the site served `index-NczabCfy.js` / `index-DLwX9K2C.css`; the
downloaded bundle is byte-for-byte identical to a local build of `main` and contains the new
`flex flex-col sm:flex-row min-h-screen bg-base` root layout and none of the old one.
`/api/health` `{"status":"ok"}`.

**Not verified in production:** the layout on a real phone -- the operator's phone could not
reach the site (plain HTTP on a bare IP); phone results are real-Chrome mobile emulation.

---

## 2026-09-24 -- PR #174: Amendment 46 (completed-header audit fixes)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `0caf69d` -> `1ab5a89` (includes PR #173's docs-only close-out)
**Frontend-only** -- no migration, no backend rebuild. Diffed against the previous deploy
before handing over commands: only `Sidebar.jsx`, `Dashboard.jsx`, `ClientsAdmin.jsx`,
`FollowUps.jsx`, `Opportunities.jsx` (plus docs) changed, nothing under `backend/`.

Fixes from the pre-next-header audit: a role refused by the API no longer sees a false
"nothing here" empty state; `site_engineer`/`ca_tax` no longer get Leads & Clients /
Opportunities / Follow-ups nav items and tabs; the Leads & Clients page is titled to match
its nav item with plain-language copy and tooltips; the Overview placeholder no longer says
"Phase 7".

**Rebuild was clean** -- `git pull` fast-forwarded `0caf69d..1ab5a89`, the frontend Docker
build completed, `/api/health` `{"status":"ok"}`. Deployment confirmed by the served frontend
bundle changing (`index-CTIu5qul.js` -> `index-DeWY-Pec.js`), not only by the pasted output.

**Live-verified in production** as `verify-director@nestaprime.local` (real UI): Leads &
Clients heading, the plain-language blurb including the Director-only flags sentence, the
Overdue/Blacklisted checkboxes present for a Director, the plain WhatsApp tooltip, the
Overview placeholder reading "arrives with Payments", and the full Director nav/tab strip
intact (nothing over-hidden). **Not verifiable in production:** the restricted-role
behaviours (`site_engineer`/`ca_tax` nav hiding, Sales not seeing the flags) -- no such
active production accounts exist. Those were verified in the real UI locally against the
identical code, and production is serving that same build.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-24 -- PR #171: Amendment 44 Phase D (Dashboard wiring + combined Follow-ups)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `2806240` -> `0caf69d` (includes PR #172's docs-only close-out)
**No migration.** Backend rebuild (`dashboard.py`) and frontend rebuild (`Dashboard.jsx`,
`FollowUps.jsx`, `App.jsx`) both needed.

The last piece of Amendment 44 / Section E step 5. The Dashboard's "Open opportunities" tile
and "Sales pipeline" panel show real counts (counts only -- no fabricated value);
`followups_due_count` now sums due Clients and due open Opportunities; "Your next moves"
lists due leads alongside clients; the Follow-ups screen is one combined queue with a
"My follow-ups" toggle that narrows leads to the signed-in user's own
(`Opportunity.created_by_id`), keeping Clients visible with an explanatory note since
Client has no owner field.

**Rebuild was clean** -- `git pull` fast-forwarded `2806240..0caf69d`, no `Running upgrade`
line (correct), backend log stamped 03:32:17 with both gunicorn workers `Application
startup complete`, `/api/health` `{"status":"ok"}`. The deploy was not run immediately
after the merge, so I confirmed it landed by polling production's `/api/dashboard` for the
new `open_opportunities_count` field and the frontend bundle name changing, rather than
assuming it. An earlier paste turned out to be the previous (Phase C) deploy's output
again -- identified by its unchanged commit hashes and `02:42` log stamps -- which is why
a deploy should be confirmed by what the *server* returns, not only by pasted output.

**Live-verified in production:** created a throwaway due-today lead ("... Phase D Verify
Lead (delete me)"); the API moved to 1 open / 1 new / 1 follow-up due; in the real UI the
Dashboard showed Open opportunities 1, Follow-ups due 1, the New bar in Sales pipeline, and
the lead in "Your next moves"; the Follow-ups screen listed it as "Due today" with the
"My follow-ups" toggle showing its explanatory note; saving a note in place persisted.
Closed the lead as Lost afterward and confirmed every count returned to 0.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-24 -- PR #170: Amendment 44 Phase C (Won -> Start Project hand-off)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `f8ed62d` -> `2806240` (also fast-forwards production past PR #169's
docs-only close-out, not separately deployed)
**No migration** -- both link columns (`Project.opportunity_id`,
`Opportunity.project_id`) shipped in PR #164's migration. Backend rebuild
(`projects.py` now validates and writes back `opportunity_id`) and frontend rebuild
(`Opportunities.jsx`, `ProjectSetup.jsx`, `App.jsx`) both needed.

A Won Opportunity linked to a Client gets a "Start Project" button that opens New Project
Setup with the client locked and a banner naming the Opportunity; the created Project and
the Opportunity point at each other. `POST /projects` rejects a non-Won, client-mismatched,
lead-only or already-converted Opportunity before creating anything.

**Rebuild was clean, no boot race this time** -- the checks ran after a `sleep 10`
following the rebuild: `git pull` fast-forwarded to `2806240`, the log showed no
`Running upgrade` line (correct, no migration), the backend container was `Up`, both
gunicorn workers logged `Application startup complete`, `/api/health` returned
`{"status":"ok"}`. The earlier deploys' transient failed health curls were purely a
paste-timing race; separating the check from the restart removed them.

**Live-verified in production:** linked the throwaway Won lead "Amendment 44 Verify Lead"
to the existing "(delete me)" client, then as `verify-director@nestaprime.local` used the
real UI: Opportunities -> "Start Project" -> confirmed the banner and locked client ->
created **P-2609-0020**. Confirmed via the API that `Project.opportunity_id` and
`Opportunity.project_id` match, and that a second attempt from the same Opportunity is
rejected (400, "This Opportunity has already started a Project"). The new project sits on
a "(delete me)" client, same throwaway convention as earlier verification projects.

**Not yet deployed:** Phase D (PR #171, Dashboard wiring + combined Follow-ups) is merged
to `main` (`1dfbbb0`) but production is still on Phase C -- the Dashboard's "Open
opportunities" tile and "Sales pipeline" panel still read "Soon" there.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-23 -- PR #168: Amendment 45 (hide admin-only client flags, add Notes field)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `0133eed` -> `f8ed62d` (also fast-forwards production past PR #167's
docs-only close-out, not separately deployed -- see its own deploy-log entry below)
**One real migration** -- `324c6521d698` adds `clients.notes` and `opportunities.notes`
(both `Text`, nullable). Frontend rebuild needed (`ClientsAdmin.jsx`/`Opportunities.jsx`
changed).

Two Leads & Clients polish fixes from a direct Director review of the Sales-facing
surface audit: Overdue/Blacklisted checkboxes now render only for a Director (previously
shown greyed-out to everyone); a general Notes/remarks field (distinct from either
entity's follow-up-specific note) on `Client` and `Opportunity`, with a textarea on
"Add a client"/"Add Enquiry" and inline edit-and-save on existing records.

**Rebuild and migration were clean** -- `git pull` fast-forwarded to `f8ed62d`, the log
explicitly showed `Running upgrade d0d627473d3c -> 324c6521d698, add notes field to
clients and opportunities (Amendment 45)`, `docker compose ... ps` showed the backend
container `Up` with no restart, gunicorn started both workers, frontend build completed,
and the final health curl (run after the frontend build, not in the same instant as the
backend restart) returned `{"status":"ok"}` -- no repeat of the earlier pasted-commands
boot race since the checks landed later in the sequence this time.

**Live-verified in production** (not just the automated suite: 20 new tests in
`test_notes.py`, full dashboard/client-follow-up/opportunities/notes suite 44 tests
re-run clean beforehand): logged in as `verify-director@nestaprime.local`, created a
client via "Add a client" with notes text and confirmed it persisted in the API response,
created an Opportunity via "Add Enquiry" with notes text and confirmed the same. Cleared
the verify client's notes back to null and moved the verify Opportunity to Lost (terminal,
harmless) afterward -- no live test data left active.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-23 -- PR #167: Amendment 44 Phase B close-out (deploy-log entry + register closure)

**Run by:** R. Patni (with AI development assistance)
**Docs-only** -- no code changes, no deploy step. Its content reached production only as
part of PR #168's `git pull` above, since it was never deployed on its own.

---

## 2026-09-23 -- PR #166: Amendment 44 Phase B (Add Enquiry UI + Opportunities screen)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `e3c0fc4` -> `0133eed` (also fast-forwards production past PR #165's
docs-only close-out, not separately deployed -- see its own deploy-log entry below)
**Frontend-only** -- no migration, no backend rebuild needed.

The UI half of the shell-first Opportunities build: "Add Enquiry" on `ClientsAdmin.jsx`
(quick-capture, no `ClientType`/full-Client fields), and a new `Opportunities.jsx` screen
(All/Leads/Clients relationship tabs, stage pill, inline stage-change and follow-up-date
editing, link-to-existing-client). Replaces the `ComingSoon` placeholder; Sidebar/tab-strip
drop the "Soon" badge.

**Rebuild was clean** -- `git pull` fast-forwarded to `0133eed`, the frontend Docker build
completed without error, files copied to `/var/www/nestaprime/dist`, `/api/health`
returned `{"status":"ok"}` (backend untouched by this deploy, no boot-race this time).

**Live-verified in production:** logged in as `verify-director@nestaprime.local`, used
"Add Enquiry" to create a lead-only Opportunity, confirmed it appeared on the
Opportunities screen under "Leads" with the "new" stage pill, linked it to an existing
throwaway "(delete me)" Client (confirmed it moved to the "Clients" filter), then set its
stage to "lost" -- left in that terminal, harmless state alongside PR #164's own earlier
throwaway Opportunity (also still lead-only, in "won").

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-23 -- PR #165: Amendment 44 Phase A close-out (deploy-log entry + register closure)

**Run by:** R. Patni (with AI development assistance)
**Docs-only** -- no code changes, no deploy step. Its content reached production only as
part of PR #166's `git pull` above, since it was never deployed on its own.

---

## 2026-09-23 -- PR #164: Amendment 44 Phase A (Opportunity model + API, Section E step 5)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `408ac1b` -> `e3c0fc4` (also fast-forwards production past PR #163's
docs-only close-out, not separately deployed -- see its own deploy-log entry below)
**One real migration** -- `d0d627473d3c` creates the `opportunities` table and adds
`projects.opportunity_id` (nullable back-link). Backend-only; no frontend rebuild needed
(nothing in `frontend/src` changed this PR).

The backend foundation for the largest single piece in the header-by-header build index:
a new `Opportunity` entity (Lead/Client distinction, pipeline stages, mandatory-
follow-up-date discipline), shipped shell-first per the approved spec -- Add Enquiry UI,
the Opportunities screen, the Won-Project hand-off, and Dashboard wiring land in
follow-up PRs. `POST /opportunities` (Add Enquiry), `GET /opportunities` (stage/
relationship filters), `PATCH .../stage`, `PATCH .../follow-up`, `PATCH .../link-client`.

**Rebuild and migration were clean** -- `git pull` fast-forwarded to `e3c0fc4`, the log
explicitly showed `Running upgrade a3c7e29f5d16 -> d0d627473d3c, add opportunities table
and project opportunity_id (Amendment 44)`, `docker compose ... ps` showed the backend
container `Up` with no restart, both gunicorn workers logged `Application startup
complete`. As with PR #162's deploy, the first pasted-together health curls (both the
direct-to-container one and, this time, the external one through nginx) failed
transiently before the workers finished booting -- re-checking `ps`/logs/curl a few
seconds later confirmed a clean, stable boot, not a real fault.

**Live-verified in production** (not just the automated suite: 23 new tests in
`test_opportunities.py`, full dashboard/client-follow-up/opportunities suite 44 tests
re-run clean beforehand): logged in as `verify-director@nestaprime.local`, created a
lead-only Opportunity via `POST /opportunities` (no `client_id`), confirmed creation
without `next_follow_up_date` is rejected (422), confirmed a stage change to `contacted`
without a fresh date is rejected (400), moved it to `won` and confirmed
`next_follow_up_date` cleared to null automatically, confirmed it appears under
`GET /opportunities?relationship=lead`. Left in place as a real (Won, terminal, harmless)
throwaway record -- no delete/rename endpoint exists yet for Opportunities, unlike
Client's own "(delete me)" convention.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-23 -- PR #163: Amendment 43 close-out (deploy-log entry + register closure)

**Run by:** R. Patni (with AI development assistance)
**Docs-only** -- no code changes, no deploy step. Its content reached production only as
part of PR #164's `git pull` above, since it was never deployed on its own.

---

## 2026-09-23 -- PR #162: Amendment 43 (Follow-ups screen, Section E step 4)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `708dc53` -> `408ac1b`
**No migration** -- `followups_due_count` is a computed field on the existing
`DashboardSummary`, not a schema change. Frontend rebuild needed (`FollowUps.jsx` is new,
`Dashboard.jsx`/`Sidebar.jsx`/`App.jsx` changed).

The concrete deliverable for Section E step 4 (Follow-ups) of the header-by-header build
index. Wires Dashboard's "Follow-ups due" KPI tile and "Your next moves" panel to real
data (both previously `ComingSoon` placeholders), and adds a real org-wide Follow-ups
screen reusing `GET /clients` -- no new list endpoint. Org-wide only: `Client` has no
owner/assigned-rep field yet, so per-rep filtering awaits the future `Opportunity.owner`
field (Section E step 5). Drops the "Soon" badge from the Sidebar/tab-strip nav item.

**Rebuild was clean** -- `git pull` fast-forwarded to `408ac1b`, backend logs showed a
clean alembic context with no pending migration (as expected), both gunicorn workers
logged `Application startup complete`. The first direct-to-container health curl
(`127.0.0.1:8000/health`) transiently failed with "Connection reset by peer" -- all the
redeploy commands were pasted together, so it fired before the workers finished booting;
re-checking logs and re-curling a few seconds later confirmed a clean boot, not a real
fault. The external health curl (`65.1.234.78/api/health`, through nginx) had already
returned `{"status":"ok"}` by that point regardless.

**Live-verified in production** (not just the automated suite: one new backend test in
`test_dashboard.py`): logged in as `verify-director@nestaprime.local`, set a real
follow-up date and note on an existing throwaway "(delete me)" test client, confirmed the
Dashboard tile went 0 -> 1, "Your next moves" showed it with today's date, the full
Follow-ups screen labeled it "Due today" with the note, then cleared the fields back to
null and confirmed the count returned to 0 -- no test data left behind.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-23 -- PR #159: Amendment 42 (Client follow-up date, Leads & Clients)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `d042931` -> `708dc53`
**One real migration** -- `a3c7e29f5d16` adds `clients.next_follow_up_date` (Date,
nullable) and `clients.follow_up_note` (String(200), nullable). Frontend rebuild needed
(`ClientsAdmin.jsx` gained the inline follow-up control).

The concrete deliverable for Section E step 3 (Leads & Clients) of the header-by-header
build index -- the "re-home" half already shipped in Amendment 36; this is the
new-capability half (Section B.1's verified gap). New `PATCH /clients/{id}/follow-up`
endpoint, `sales`/`pm`/`director` (not Director-only -- Sales is the primary daily user),
deliberately not audit-logged (routine reminder, not a governance-relevant fact like
blacklist/consent) and deliberately not mandatory (distinct from the mandatory-follow-up
discipline already decided for the future Opportunity entity).

**Rebuild and migration were clean** -- `git pull` fast-forwarded to `708dc53`, the log
explicitly showed `Running upgrade 9e8bdbaf6219 -> a3c7e29f5d16, add client follow-up
date and note (Amendment 42)`, both gunicorn workers logged `Application startup
complete`, `curl .../health` returned `{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: 7 new tests in
`test_client_follow_up.py`, full client suite 65 tests re-run clean): reactivated
`verify-director@nestaprime.local`, set a real follow-up date and note on a live client,
confirmed it persisted after reload, cleared it back to null afterward -- this test
modified an existing real client record's own field (not a throwaway "(delete me)"
record), so it was cleaned up rather than left as a known leftover.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-22 -- PR #151: Amendment 36 (Nav shell + Dashboard shell, CRM restructure Phase 1)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `59c7301` -> `0970847`
**No migration, no seed script** -- frontend-only. Backend was rebuilt anyway per the
standard redeploy sequence (clean no-op, no schema change).

Phase 1 of the 9-step header-by-header CRM build index
(`docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md` Section E). Replaces the
top-nav dropdowns (`App.jsx`'s old `navGroups`) with a left sidebar
(`frontend/src/Sidebar.jsx`) carrying the confirmed CRM headers, and rebuilds
`Dashboard.jsx` as an "Overview" shell matching the chosen CRM reference layout. Two
tiles (Pending Quotations, Active Projects) show real data from the existing `/dashboard`
endpoint, unchanged; Opportunities/Follow-ups/Payments and two panel placeholders
(`ComingSoon.jsx`) honestly read "Soon"/"Coming soon" rather than a fabricated number,
since those capabilities don't exist yet. Vendor/Tools/Reports/Admin/Education re-homed
into a temporary "More" menu with their exact old sub-groupings and role gates intact.

**Rebuild was clean** -- `git pull` fast-forwarded to `0970847`, backend rebuild was a
no-op (cached layers, no migration ran), frontend rebuild+`nginx` publish succeeded,
`curl .../api/health` returned `{"status":"ok"}`.

**Live-verified in production**: reactivated `verify-director@nestaprime.local`, logged
in, confirmed the new sidebar and Overview dashboard render with real live figures
(Pending Quotations: 3, Active Projects: 12) and every not-yet-built tile/panel correctly
shows "Soon"/"Coming soon". A side-by-side comparison artifact against the chosen CRM
reference was produced and reviewed
(`https://claude.ai/artifact/A7hVLbMZM52AzfA18t9YyY`). Both director and sales roles were
also verified locally before merge.

**`verify-director@nestaprime.local` intentionally left active** -- Director decision, to
stay available across the next several amendments' live verification rather than
reactivating it per-deploy; one consolidated deactivation once that batch is audited. See
Amendment 36's Annexure-2.md entry for the full note. **Not yet closed** -- must be
deactivated before this is treated as done.

## 2026-09-22 -- PR #149: Amendment 34 (Vendor deactivation + duplicate-vendor guard)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `b075d41` -> `3e7e5b0`
**One real migration** -- `9e8bdbaf6219` adds `vendors.is_active` (boolean, default
`True`). No frontend rebuild needed (no UI built for this yet -- the flag is set via
`VendorCreate`/the updated `PATCH /vendors/{id}` only).

Self-identified during the seventh proactive gap audit, the last of that batch (32-34).
`Vendor` had no `is_active` column at all, unlike `Hub`'s own explicit retire-without-
delete convention, and no DELETE endpoint either -- a vendor could never be retired once
created. `create_vendor` also had zero duplicate check on `name`/`gstin`, unlike
`create_hub`'s explicit `409` in the same codebase. Fixed by adding `is_active` (default
`True`, deactivation not deletion -- a vendor may be referenced by historical Price
Requests/POs/RateHistory rows), `list_vendors`'s `include_inactive` param, and a `409`
duplicate guard on `name`/`gstin` (only when `gstin` is set, since `null` legitimately
means unregistered).

**Rebuild and migration were clean** -- `git pull` fast-forwarded to `3e7e5b0`, the log
explicitly showed `Running upgrade ac1785734f0f -> 9e8bdbaf6219, add vendor is_active flag
(Amendment 34)`, both gunicorn workers logged `Application startup complete`, `curl
.../health` returned `{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: 6 new tests in
`test_vendor_products.py`, full backend suite 1217 passed): reactivated
`verify-director@nestaprime.local`, created a throwaway vendor (`is_active: true` by
default), confirmed a duplicate name and a duplicate GSTIN were both rejected `409`,
deactivated the vendor and confirmed it dropped out of the default `GET /vendors` listing
while remaining retrievable directly by id and via `include_inactive=true`. Account
deactivated in the script's own `finally` block, confirmed `is_active: False` at the end.

**Known leftover:** one more throwaway record, "Amendment 34 Verify (delete me)" vendor,
remains in production data -- same reasoning as every prior deploy's leftovers (no delete
endpoint by design; Director has said to leave these as-is).

**This closes out the entire seventh gap-audit batch** (Amendments 32-34), and with it, all
34 amendments registered so far are now implemented and deployed to production.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-22 -- PRs #146-#147: Amendments 32-33 (Override guard fix, Skip Request reject path)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `4bd9420` -> `b075d41`
**One real migration in this batch** -- `ac1785734f0f` (Amendment 33) adds
`skip_requests.rejection_reason` and a `REJECTED` value to the `skip_request_status`
Postgres enum. Amendment 32 is backend-only, no schema change. No frontend rebuild
needed for either.

Both self-identified during the seventh proactive gap audit. Amendment 32:
`create_override`'s Amendment-22 numeric guard only inspected the caller-supplied
`master_value`, never the real Setting -- a fabricated non-numeric `master_value` skipped
the check entirely. Fixed by looking up the real value server-side; when none exists (most
K.1 constants run on a hardcoded default with no `Settings` row), the check is skipped
exactly as before rather than 404ing, a narrowing agreed during implementation after
discovering that architecture (see Annexure 2's own Amendment 32 closing note). Amendment
33: `SkipRequestStatus` had no `REJECTED` value and no reject endpoint, so a pending
request nobody wanted to approve permanently blocked every future skip request on that
project; fixed with a new status, a reject endpoint, and a symmetric guard on
`create_cost_sheet`.

**Rebuild and migration were clean** -- `git pull` fast-forwarded to `b075d41`, the log
explicitly showed `Running upgrade 323ecc35b9df -> ac1785734f0f, add skip request REJECTED
status + rejection_reason (Amendment 33)`, both gunicorn workers logged `Application
startup complete`, `curl .../health` returned `{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: Amendment 32's tests in
`test_settings.py`/`test_override_validation.py`, Amendment 33's 8 new tests in
`test_skip_requests.py`; full backend suite 1203 passed then 1211 passed across the two
PRs): the first verification script for Amendment 32 hit a false-negative-shaped result on
`contingency_structure_percent` -- a direct DB query confirmed this setting genuinely
already had a real `Settings` row (`5.0`, dated 2026-01-01) in production, so the `422` it
returned was correct behavior, not a bug; the test's own assumption (that key would have no
row) was wrong, not the product. Re-ran cleanly against a guaranteed-unconfigured key
instead: fabricated `master_value` rejected (`422`), a real override recorded the correct
server-computed `master_value` (`6.0`), and an override against the confirmed-unconfigured
key still succeeded with the new placeholder text. Amendment 33: a normal Cost Sheet build
was blocked (`400`) while a skip request was pending; rejecting it recorded the reason;
a new skip request could then be raised (deadlock resolved); the normal Cost Sheet path
was blocked again by that second pending request. Account deactivated in each script's own
`finally` block, confirmed `is_active: False` each time.

**Known leftover:** two more throwaway records, "Amendment 32 Verify (delete me)" (rate
overrides only, no client/project) and "Amendment 33 Verify (delete me)" (client/project/
two skip requests), remain in production data -- same reasoning as every prior deploy's
leftovers (no delete endpoint by design; Director has said to leave these as-is).

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-21 -- PRs #140-#142: Amendments 29-31 (missing audit-log trails)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `5f27fb3` -> `4bd9420`
**Backend only** -- no new migration (none of the three changed the schema), no
frontend rebuild needed.

Self-identified during a sixth proactive gap audit against the register, targeting
fresh territory (user/auth management, reports, attachments, client management,
audit-log consistency, and not-yet-audited reference-data modules). Three findings
registered and specced: Amendment 29 -- `update_client_flags` (blacklist/overdue,
Director-only) had no audit trail, unlike its sibling `update_client_consent` right
below it. Amendment 30 -- `release_report` had no audit trail, unlike the identical
`release_quotation` pattern. Amendment 31 -- `client_signatories.py` had no audit trail
at all, despite these records gating whether a client-side approval on an
`approval_evidence` attachment is considered legally valid. All three fixed by adding
`write_audit_log_entry` calls matching this codebase's existing conventions (a
changed-field loop for 29 and 31's update path, an unconditional log for 30's
Director-only transition, a "created" entry for 31's create path).

**Rebuild was clean** -- `git pull` fast-forwarded to `4bd9420`, the backend rebuilt and
started without incident, both gunicorn workers logged `Application startup complete`,
`curl .../health` returned `{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: 4 new/updated tests in
`test_client_flags.py`, 1 in `test_reports.py`, 3 in `test_client_signatories.py`; full
backend suite 1201 passed across the three implementation PRs): reactivated
`verify-director@nestaprime.local`, then in one script: set `blacklist_flag` on a
throwaway client and confirmed a `client` audit entry (`False` -> `True`); released a
Margin report and confirmed a `report` audit entry (`draft` -> `released`); created a
signatory and confirmed a `client_signatory` "created" entry naming it, then updated its
`designation` and `is_active` and confirmed two more correctly-valued entries. Account
deactivated in the script's own `finally` block, confirmed `is_active: False` at the
end.

**Known leftover:** one more throwaway record, "Amendments 29-31 Verify (delete me)"
client/project/estimate/quotation/report/signatory, remains in production data -- same
reasoning as every prior deploy's leftovers (no delete endpoint by design; Director has
said to leave these as-is).

**Smoke test:** confirmed working end-to-end as described above, not just a
health-check curl.

---

## 2026-09-20 -- PR #136: Amendment 28 (Open Projects fix + calibration exclusion)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `e474aa6` -> `5f27fb3`
**Backend only, first real migration of this batch** -- `323ecc35b9df` adds
`projects.is_calibration` (boolean, default `False`). No frontend rebuild needed (no UI
built for this yet -- the flag is set via `ProjectCreate`/the new PATCH endpoint only).

Self-identified during the same fifth proactive gap audit as Amendments 26-27. Part A:
`open_projects_count` excluded a project the moment *any* Quotation on it reached
Won/Lost, permanently -- so a project re-bid after Amendment 26 made that possible would
still never show as Open again. Fixed by deriving `closed_project_ids` from projects with
no live (non-Won/Lost) Quotation, so only a project where *every* Quotation is closed
counts as closed. Part B: adds `Project.is_calibration`, settable at creation or via a new
Director-only `PATCH /projects/{id}/calibration`, excluded from all three dashboard
summary tiles.

**Rebuild and migration were clean** -- `git pull` fast-forwarded to `5f27fb3`, the
backend rebuilt and started, the log explicitly showed `Running upgrade b98a7f5bc39a ->
323ecc35b9df, add project is_calibration flag (Amendment 28 Part B)`, both gunicorn
workers logged `Application startup complete`, `curl .../health` returned
`{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: 20 new/updated tests in
`test_dashboard.py`, full backend suite 1194 passed): reactivated
`verify-director@nestaprime.local`, ran the full re-bid cycle on a throwaway project --
Open count went 10 -> 11 (live Released quotation) -> 10 (quotation marked Lost, correctly
still closed) -> 11 again (fresh Estimate + Quotation after the Lost one, correctly Open
again). A calibration-flagged project didn't move `open_projects_count` at all, and
sending a calibration project's Estimate didn't move `pending_estimates_count`. The
Director-only PATCH backfill mechanism was exercised live too (flagging the restarted
project brought the count back to 10). Account deactivated in the script's own `finally`
block, confirmed `is_active: False` at the end. The verification script appears to have
run twice (14 minutes apart) leaving 4 throwaway projects instead of 2 under "Amendment 28
Verify (delete me)" -- harmless, same known-leftover pattern as below.

**Manual backfill.** The Mathura/Noida/Bathinda projects this Amendment's registered text
refers to (see Annexure 2's own closing note) do not exist as rows on this production
server -- a direct DB search across all 15 production projects by city, client name, and
notes found zero matches. The server's actual calibration data turned out to be two
projects under client "Pathankot Badminton Court (FY23-24 actual, calibration)"
(`P-2609-0002`, `P-2609-0003`) -- self-identified by name -- confirmed and flagged
`is_calibration=True` via a direct script using the same DB session the API uses, verified
by re-reading both rows back afterward.

**Known leftover:** beyond the usual "(delete me)" throwaway records from prior deploys,
this deploy added 4 more under "Amendment 28 Verify (delete me)" (see above) -- same
reasoning as every prior deploy's leftovers, no delete endpoint by design.

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-20 -- PR #134: Amendment 27 (vendor reply GST-basis conversion)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `3e9534e` -> `73673b6`
**Backend only** -- no new migration (no schema change), no frontend rebuild needed.

Self-identified during the same fifth proactive gap audit as Amendment 26:
`use_vendor_reply` applied a vendor's parsed rate literally onto `RateItem.rate`/
`CostSheetLine.rate` regardless of whether the reply was GST-inclusive or exclusive, even
though `VendorReply.parsed_gst_basis` was already captured and stored -- a GST-inclusive
reply silently overstated the cost basis by the embedded GST% on every downstream Cost
Sheet/Estimate/Quotation, with no error or warning. A related gap in the same function:
applying a reply to a Cost Sheet line never checked the line's `rate_item_id` matched the
price request item the reply actually answers. Fixed via a GST-basis conversion
(`ex_gst_rate = parsed_rate / (1 + applicable_gst_percent / 100)`, item-override-else-
global resolution order matching `pricing.py`), a required `confirmed_ex_gst` flag for
ambiguous replies, and the missing cross-check.

**Rebuild was clean** -- `git pull` fast-forwarded to `73673b6`, `docker compose ... up -d
--build backend` built and started without incident (one terminal-paste artifact on the
first `curl` attempt, re-run cleanly), both gunicorn workers logged `Application startup
complete`, `curl .../health` returned `{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: 26 tests in
`test_vendor_price_requests.py`, full backend suite 1188 passed): reactivated
`verify-director@nestaprime.local`, created a throwaway rate item/vendor/price request,
captured a reply of "Rs 118/kg incl GST" against the live 18% global `gst_rate_percent`
setting, applied it to the Rate Master -- resulting rate `100.0`, the correct ex-GST
figure, not `118.0`. Separately captured a reply with no parseable GST wording and
confirmed applying it without `confirmed_ex_gst` was rejected with `422`. Account
deactivated in the script's own `finally` block, confirmed `is_active: False` at the end.

**Known leftover:** a sixth throwaway record, "Amendment 27 Verify (delete me)" rate
item/vendor/price request, remains in production data -- same reasoning as every prior
deploy's leftovers (no delete endpoint for either by design; Director has said to leave
these as-is).

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-20 -- PRs #130-#132: Amendment 26 (re-quote crash fix)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `89f703a` -> `df47162` (PR #130 registered Amendments 26-28; #131
recorded the Sections 32-34 spec approvals -- both docs-only; #132 is the
implementation, rebased onto `main` once as #131 merged first -- clean rebase, unrelated
files)
**Backend only** -- no new migration (no schema change), no frontend rebuild needed.

Self-identified during a fifth proactive gap audit against the register: `create_estimate`,
`create_quotation`, and both document-creation sites inside `create_fast_track_quotation`
all hardcoded `document_no`'s revision to `1` with no check for an existing document on
the project, so the second Estimate/Quotation a project ever needed (e.g. re-bidding a
project whose earlier Quotation went Lost) collided against the `document_no` unique
constraint and crashed with an unhandled `IntegrityError` -> 500. `revise_estimate`/
`revise_quotation` couldn't help either, since both require the document being revised to
still be Sent. Fixed via `_next_fresh_document_revision(db, model, project_id)`, computing
`max(existing revision_major) + 1` for the project -- same shape Amendment 23 already uses
for `_generate_project_no`/`_po_number`.

**Rebuild was clean** -- `git pull` fast-forwarded to `df47162`, `docker compose ... up -d
--build backend` built and started without incident, both gunicorn workers logged
`Application startup complete`, `curl .../health` returned `{"status":"ok"}`.

**Live-verified in production** (not just the automated suite: 4 new tests in
`test_estimate_quotation_revision.py`, full backend suite 1183 passed): reactivated
`verify-director@nestaprime.local`, created a throwaway project end-to-end through a Sent
Estimate -> Released Quotation -> marked Lost, then created a second Estimate directly
(not via `/revise`) -- `201`, `EST-2609-0011-R2`, `revision_major: 2` -- followed by a
second Quotation the same way -- `201`, `NPQ-2609-0011-R2`, `revision_major: 2`. Neither
crashed. Account deactivated in the script's own `finally` block regardless of outcome,
confirmed `is_active: False` at the end.

**Known leftover:** a fifth throwaway record, "Amendment 26 Verify (delete me)"
client/project/two Estimates/two Quotations, remains in production data -- same reasoning
as every prior deploy's leftovers (no delete endpoint for either by design; Director has
said to leave these as-is).

**Smoke test:** confirmed working end-to-end as described above, not just a health-check
curl.

---

## 2026-09-20 -- PRs #126-#128: Amendments 24-25 (dynamic GST label, rate import
field-update fix)

**Run by:** R. Patni (with AI development assistance)
**Commit range:** `89f703a` -> `f8a941b` (PR #126 was the two approved specs,
docs-only; #127 and #128 are the two independent implementation PRs, each rebased onto
`main` twice as the ones before it merged -- clean rebases both times, unrelated files)
**Backend only** -- no new migration (neither amendment changed the schema), no
frontend rebuild needed.

Both amendments were self-identified during a fourth proactive gap audit against the
register: Amendment 24 fixes the Quotation PDF and Billing Handoff export both
hardcoding "GST @ 18% (flat)"/"18% flat" regardless of the actual, Director-
configurable, possibly-blended rate (Note R1's own HSN-9506 5% equipment lines) -- the
label is now back-derived from the document's own frozen `gst_amount`/
`selling_after_discount`, the only value that's guaranteed to match the rupee amount
already printed next to it. Amendment 25 fixes `import_rate_items` silently discarding
non-rate field edits (vendor, HSN/SAC, city, labour category, commodity-watch flag)
whenever a row's rate was unchanged, reporting the row as "unchanged" instead of
applying the edit -- a real data-loss risk on a documented bulk-edit workflow (a blank
Rate cell is an explicit, intentional "leave the rate untouched" signal, not an edge
case).

**Deploy interrupted by a real power cut partway through the live smoke test** -- the
backend rebuild/restart itself completed and was confirmed clean beforehand. The EC2
instance came back on its own; `docker compose ps` after reconnecting showed both
containers had survived/restarted cleanly (`restart: unless-stopped`), and `curl
.../api/health` returned `{"status":"ok"}` before smoke testing resumed. Two of the
smoke-test script attempts crashed partway through (a missing Cost Sheet-creation step
before the Estimate call; then a `client_id` field assumption that didn't match `GET
/projects`'s actual response shape) -- both crashes briefly left
`verify-director@nestaprime.local` reactivated before the script's own cleanup step
could run. Caught and fixed immediately both times by having a follow-up command
deactivate the account before proceeding; the final working script was rewritten with a
`try/finally` so the account is deactivated regardless of whether the rest of the
script succeeds, closing that gap for future passes too.

**Live-verified both amendments in production**, not just via the automated test suite
(149 tests total across both PRs, all passing in CI): raised a full real Quotation
through release/send/mark-won on a throwaway client, downloaded its PDF, and confirmed
(via `pypdf.PdfReader`'s actual text extraction, not a naive byte-decode -- a first
attempt using the latter produced a false negative, caught and corrected before trusting
it) that it prints "GST @ 18.0%" and no longer contains "(flat)"; the Billing Handoff
export showed "Total (GST-inclusive, 18.0%)". Amendment 25: imported an Excel row
changing only the vendor with the Rate cell left blank -- the row came back as
`updated` (not `unchanged`), the vendor was applied, and the rate stayed untouched at
its original value.

**Known leftover:** a fourth "Deploy Smoke Test Client 2 (delete me)" / project /
quotation and one "Deploy Smoke Test Item (delete me)" rate item remain in production
data, same reasoning as prior deploys' leftovers (no delete endpoint for either by
design).

**Smoke test:** confirmed working end-to-end as described above, not just a
health-check curl.

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
