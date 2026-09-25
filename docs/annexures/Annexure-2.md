# Annexure 2 — Proposed Amendments to the NestaPrime Estimator Application

**Version 1.11 | Date: 16 September 2026 | Status: DRAFT — Pending Director Approval**

Source: `Annexure-2_NestaPrime-Estimator_Amendments.docx`, prepared by R. Patni (with AI
development assistance). Committed here as the governing change register — see
[`README.md`](../../README.md) for how it fits into the rest of the project record.

**v1.11 changes (16 September, register reconciled against shipped code):** Amendments
1–10 were recorded in v1.10 as entirely unimplemented ("nothing in this version has been
implemented"), but that stopped being true almost immediately — by 12–14 September, PRs
#23–#47 had already shipped real, working implementations for most of them without the
register being updated to say so. This pass checked each of Amendments 1, 2, 3, 5, 6, 7,
8, 9, 10 against the actual codebase (file-by-file, with `git log` PR/date evidence) and
records the true status under each entry below: **fully implemented** — 1, 3, 6, 7, 9;
**partially implemented**, with the specific gap named — 2, 5, 8, 10. No code changed in
this pass; this is a documentation correction only, same discipline as the deploy-log
corrections recorded in `docs/ops/deploy-log.md`. (Amendment 4 already carries its own
accurate status further below and wasn't part of this check; Amendments 11–13 were
already correctly marked.)

**v1.10 changes (12 September, review session 2):** Amendment No. 4 expanded with
acceptance criteria confirmed live on production, plus refinements found while
reviewing the dashboard and nav with a sales-rep workflow in mind (project search,
per-client project list, naming clarity, plain-language activity feed, admin/user
role separation). Amendment No. 5 expanded to absorb the 12 September parking-lot
item (Director decision: merge, not a new amendment). Note R3 added for two
launch-night housekeeping items that never got a formal home.

---

## 0. Governing Philosophy — The NPS Picture

The app serves one conversation: what the client HAS → what he WANTS → the NPS solution →
the PRICE → cross-sell. Ultimate goal: "the app's purpose is to be fully customizable to
meet specific business requirements." Every amendment must serve these points.

## 1. Change Process

1. Record in this register.
2. Director approves → complete amended specification prepared.
3. Only then implement (branch → PR → tests → merge → deploy).

**REGISTER FREEZE RULE**: No new amendments until the current wave ships. New ideas go to
a parking lot list, reviewed at each wave's completion.

## 2. Register of Proposed Amendments

### Amendment No. 1 — Brand-Themed and Animated UI (Match Company Website)
Dark premium theme, gold `#c9a227` accents, animated sport-tile selection with court
diagram, subtle motion (0.2–0.3s). "The user is not bored and wants to work." Frontend
styling only.

**Implemented 12 September 2026 (PRs #25, #26):** the gold token (`--color-gold:
#c9a227`) is defined in `frontend/src/index.css`; `SportSelection.jsx`'s `CourtDiagram`
renders an inline SVG scaled to the sport's real playing dimensions, and sport-tile/button
transitions use `duration-200`/`duration-250` — inside the spec's 0.2–0.3s range.

### Amendment No. 2 — Simplified "New Project Setup" Form
Blind-quoting principle: 5 required fields (Client · Sport · City · Dimensions · Base
scope/status); soil type, distance, court count, site access, power/water removed (→
T&C); Quick vs Detailed modes.

**Partially implemented 12 September 2026 (PR #23):** `ProjectSetup.jsx` has a working
Quick/Detailed mode toggle (Quick by default, auto-forced to Detailed for Government
clients); soil_type/site_access/power_available are hidden or optional in Quick mode via
field settings rather than moved to T&C text. **Gap:** Quick mode asks only 4 fields, not
5 — Dimensions is shown as read-only informational text, not something the user actually
enters in Quick mode.

**Verified 19 September 2026 (re-checked against current code, not assumed from this
entry's own older text):** still a real gap, confirmed unchanged since PR #23 --
`ProjectSetup.jsx`'s Quick form still shows Dimensions as plain text with no `onChange`,
and `handleQuickSubmit` still hardcodes every dimension-adjacent field. The real cause
isn't a missing form field, though: dimensions live on `ProjectSport`, set via
`SportSelection.jsx`'s `CourtSize`, for *both* modes -- Detailed mode's own form has no
literal "Dimensions" field either. Detailed mode routes through Sport Selection after
creation (`App.jsx`'s `onProjectCreated` → `screen="sports"`); Quick mode instead skips
straight to Scope (`onQuickSetupComplete` → `screen="scope"`), so the one screen where
dimension entry genuinely happens is reachable in Detailed mode and skipped in Quick
mode. Quick mode's own copy is also stale: "(customizable once Amendment 9 ships)" --
Amendment 9 shipped the same day that text was written. Spec for closing this:
`docs/annexures/Section-21-specs.md`.

**Implemented 19 September 2026 (PR #105, deployed to production same day -- see
`docs/ops/deploy-log.md`):** `onQuickSetupComplete` now routes to `screen="sports"`,
matching `onProjectCreated` -- Quick setup lands on Sport Selection with the picked
sport already added, reusing the exact validated `CourtSize` dimension-entry path
Detailed mode already had. Stale "(customizable once Amendment 9 ships)" copy fixed.
Live-verified: the "Customize size" control reveals real, working L(ft)/W(ft) inputs.
Amendment 2 is now fully implemented.

### Amendment No. 3 — "Complete Your Facility" Cross-Sell at Estimate Step
At the Estimate step, suggest 4–5 sport-matched add-ons (lighting, fencing, seating, AMC)
with prices and own margins; one-tap add; never forced.

**Implemented 13 September 2026 (PR #39, spec PR #38):** `backend/app/api/cross_sell.py`
returns up to 5 sport-matched add-ons (lighting/fencing/seating/AMC/other), each carrying
its own cost/margin; `Documents.jsx`'s `OptionAddons` renders them inside the Estimate
option UI with one-tap add/remove, cost/margin stripped for the Sales role. Never forced.

### Amendment No. 4 — Main Dashboard + Guided Navigation
Business-summary dashboard; link back to dashboard from every section; guided step-path
with progress bar; menu grouped Daily Work / Management / Admin. "The app itself is the
training."

**Confirmed live on production (12 Sept validation run) — these are Amendment 4's
acceptance criteria, not separate asks:** no logout control anywhere in the UI; no
screen to browse or reopen an existing project (the "Existing client" picker only
starts a *new* project; the Clients directory has no per-client project links); the
"Back to project" button always opens a blank New Project Setup screen instead of
resuming anything; the User Management screen exists but isn't reachable from any menu.

**Refinements added 12 Sept (review session 2, sales-rep workflow check):**
- The dashboard's project list needs search/filter, not just "last N recent" — a
  recent-only list stops helping once the project count grows past a screenful.
- The Clients page itself needs a per-client project list, not just the global
  recent-projects list on the dashboard — this is the specific half of the
  production gap above that a dashboard alone doesn't fix.
- "Pricing Calculator" (nav item) vs. the actual Cost Sheet → Estimate → Quotation
  flow needs a naming decision so a new user isn't left guessing which one produces
  a real quotation.
- **Admin and user accounts are genuinely separated, not just visually grouped**
  (Director instruction, 12 Sept): Master Settings, Sports & Scope Admin, Audit
  Log, and User Management are hidden entirely for any role other than
  Director/Admin — not placed under an "Admin" heading that every role still sees.
  No unused headers shown to a role that can't act on them. This is pulled forward
  from Amendment 6a as the minimum viable slice.
- The Recent Activity feed renders in plain business language ("Dimensions updated
  for P-2609-0002: 60×30 → 30×60 m", "New PM account created") — not raw
  field-level diffs (`actual_dimensions: NonexNone → NonexNone`, `is_active: True →
  False`). Raw diffs stay on the Audit Log screen only.
- The dashboard's project list tags or filters out calibration/test projects (see
  Note R1) so real client work isn't crowded by validation data.

**Bugs bundled into this amendment's build (logged here so they aren't lost, not new
scope):** dimensions render as literal text `NonexNone` when blank instead of "Not
set"; today's nav bar has inconsistent spacing (Clients/Reports/Price Requests sit
tighter than the rest of the row) — moot once this amendment replaces the nav, worth
a direct fix only if this amendment slips.

**Verified 18 September 2026 (re-checked against current code, not assumed from this
entry's own older text):** four of the five 12 Sept findings are now closed, mostly as
a side effect of Amendment 12's nav/dashboard restructure rather than direct fixes to
this amendment: a real "Log out" control exists in the nav; `AllProjects.jsx` plus the
Dashboard's drill-through give a genuine project browse-and-reopen path; "Back to
project" is now a "↩ Resume {project_no}" button (`App.jsx`) that returns to the exact
project-stage screen with `activeProject` state intact, not a blank New Project Setup
form; User Management is reachable at Admin → Master Settings → "User management" tab
(Director-only). **Still open:** the Clients page itself still has no per-client
project list — `ClientsAdmin.jsx` shows only flags/consent controls, nothing
project-related; finding a client's projects today means going to Projects and typing
the client's name into free text, not clicking through from the client itself. This is
exactly the "specific half" the 12 Sept refinement above predicted a dashboard-only fix
wouldn't close.

**Continued 18 September 2026:** Director asked to check Amendment 4's five findings
against current code ("check Amendment 4's items"); given the verification above,
confirmed proceeding with both closing this entry and registering the one remaining gap
("yes, both"). Spec for closing the per-client project list, named above:
`docs/annexures/Section-19-specs.md`.

**Implemented 18 September 2026 (PR #96, deployed to production same day -- see
`docs/ops/deploy-log.md`):** `GET /projects` gained an additive `client_id` filter;
`ClientsAdmin.jsx` gained a collapsed-by-default "Projects" expand per client row,
reusing `AllProjects.jsx`'s own row shape rather than redesigning it. Pure data-wiring,
no new tables -- `Project.client_id` already existed and already drove real Cost
Sheets. Amendment 4 is now fully closed, all five original findings accounted for.

### Amendment No. 5 — Customizable Forms: Admin Controls Compulsory Fields
Every dropdown gets a "None" option; admin sets each field compulsory/optional/hidden
from Master Settings. Phase 1: None options + dashboard. Phase 2: field-settings panel.

**Merged in 12 Sept (Director decision — was parking-lot, reconciled as scope of this
amendment, not a separate one):**
- **Dropdown "Others" rule** — append "Others" to every dropdown component in the
  app; selecting it dynamically renders a text input below; the typed text becomes
  the display label on Cost Sheets and Quotation PDFs.
- **Custom Notes component** — a reusable "+ Add Note" button on Project Setup, Cost
  Sheet, and Estimate screens; toggles a multi-line textarea for unstructured
  remarks; persisted on the Project record; passed through to the Quotation PDF
  under "Special Remarks / T&C".

**Partially implemented 13–14 September 2026 (PR #37 Phase 1, PR #44 Phase 2):**
`field_setting.py`/`field_settings.py` give the Director compulsory/optional/hidden
control from Master Settings; `SelectWithOther.jsx` implements the "Others" rule
correctly; `CustomNotesPanel.jsx` is a real reusable "+ Add Note" component feeding the
Quotation PDF's Special Remarks section. **Gaps:** field-settings governance is scoped to
only 5 fields (soil_type, distance_km, number_of_courts, site_access, power_available),
not "every field"; the "Others" rule is wired into just 2 dropdowns (Category, Vendor in
`RateSheet.jsx`), not every dropdown in the app; a "None" option is only confirmed on
those same 5 governed fields, not app-wide.

**Correction, 19 September 2026 (re-checked against current code):** the first two gaps
above are unchanged and confirmed still real (`GOVERNED_FIELD_KEYS` in
`backend/app/api/field_settings.py` is still exactly those 5 fields; `SelectWithOther`
is still only used on Category and Vendor in `RateSheet.jsx` — neither has changed since
PRs #44/#37). The third claim was imprecise: a literal "None" option only exists on 3 of
the 5 governed fields (`soil_type`, `site_access`, `power_available` — all `<Select>`s);
`distance_km`/`number_of_courts` are plain number inputs with no dropdown to put a
"None" option on, so field-settings governance never gave them one. Separately, and not
placed there by this amendment's own governance mechanism at all, two unrelated
dropdowns already show a selectable "None" on their own: `RateSheet.jsx`'s Vendor field
(via `SelectWithOther`'s own default when not `required`) and its Labour category field
(a hand-written `<option value="">None (uses blended fallback %)</option>`, nothing to
do with field-settings). Bottom line is unchanged -- nowhere close to app-wide -- but the
specific field count in the original claim didn't survive a line-by-line check.

**Continued 19 September 2026 (Director instruction):** *"spec Amendment 5."* Proposes
a bounded next increment for each of the two real gaps above, not the literal "every
field"/"every dropdown" reading: adding `water_available` to field-settings governance
(Amendment 2's own named pair with the already-governed `power_available`, left out for
a UI-shape reason rather than a technical blocker), and wiring City/District into the
`SelectWithOther` rule (already has an inert, non-functional "Other" placeholder today).
Also surfaces, without resolving, a contradiction between an old unapproved draft
(`Section-6-phase2-specs.md`) and the reasoning actually shipped in
`field_setting.py`'s docstring. Spec: `docs/annexures/Section-22-specs.md`.

**Implemented 19 September 2026 (PRs #108-109, shipped as two independent PRs per
Director instruction, deployed to production same day -- see
`docs/ops/deploy-log.md`):** `water_available` joined `GOVERNED_FIELD_KEYS`, its Quick
checkbox replaced by a Select matching `power_available`'s exact pattern (new
migration made the column nullable); City/District wired into `SelectWithOther` on
both Quick and Detailed mode, replacing the old inert "Other" placeholder. Both
live-verified via the real `POST /projects` network payload before either PR was
opened. Amendment 5 is now fully implemented -- all three original gaps (governance
scope, Others rule, None-option precision) closed or corrected.

### Amendment No. 6 — User Rights Management + Reporting & Oversight
6a: role-based permissions (what each role can see/do). 6b: admin reviews all quotations
and daily activity. 6c: reports for daily / weekly / monthly / full-year / custom ranges.

**Implemented 13–14 September 2026:** 6a — `RolePermissionsViewer.jsx`, a read-only
mirror of the backend's `require_roles()` gates (PR #33, 13 Sept). 6b —
`AllQuotations.jsx`, Director-only cross-project browse with CSV/PDF export (PR #47, 14
Sept), plus the pre-existing Director-only `audit_log.py` for daily activity. 6c —
`Reports.jsx`'s `PERIOD_PRESETS` (today/this_week/this_month/this_year/custom) matches
the spec exactly (PR #32, 13 Sept).

### Amendment No. 7 — Vendor & Product Master
Vendor lists with vendor codes; products with approximate pricing under each vendor;
feeds rate sheet and price-update requests.

**Implemented 13 September 2026 (PR #37):** `models/vendor.py` (vendor_code, city,
category, GSTIN, reliability score) and `models/product.py` (per-vendor approx_price);
`VendorsAdmin.jsx` is a real Vendor Master screen with nested product management.
**Nuance:** the feed into the rate sheet is indirect — it happens through vendor
price-request replies (`price_requests.py`'s `use_vendor_reply()` writes the vendor onto
a `RateItem`), not a direct link from `Product.approx_price` onto a rate item.

### Amendment No. 8 — Communication & Integrations (WhatsApp, Email, Telegram)
Document sharing and messaging from the app with delivery status. Opportunity:
investigate the company's existing wa-gateway server before any paid BSP. Telegram
easiest to start. Largest build; after Amendments 1–7.

**Partially implemented 13 September 2026 (PR #41 — title itself scopes to WhatsApp +
Telegram only):** `services/wa_gateway.py` and `services/telegram.py` make real
provider calls; `models/message.py`'s `MessageStatus` (RECORDED/SENT/DELIVERED/FAILED)
tracks real SENT/FAILED status, reconciled via `wa_gateway_webhook.py`. **Gap: Email was
never built** — the model's own docstring states no SMTP provider is wired up; an email
"send" is just a manually confirmed record, never provider-verified. `DELIVERED` status
is defined but neither provider actually sets it (no delivery-receipt API from either).

**Continued 18 September 2026 (Director instruction):** *"Amendment 8, add real email
sending."* Spec for closing the Email gap named above: `docs/annexures/Section-17-specs.md`.

**Implemented 18 September 2026 (PR #89):** `services/email_gateway.py` closes the Email
gap named above — a thin SMTP client matching the exact `wa_gateway.py`/`telegram.py`
pattern (blank `SMTP_*` config fails fast, a send failure sets `Message.status = failed`
immediately, no retries/queueing). `create_message()`'s real-send dispatch now covers all
three channels. Live browser verification (SMTP still unconfigured) surfaced a real
frontend gap missed in the initial implementation — `MessagesPanel.jsx` still hard-coded
email as a provider-less, log-only channel (banner text claimed email "does not actually
send anything"; the "Attach PDF" checkbox was hidden for email) — fixed in the same PR
before merge. Full backend suite: 1132 passed; CI green; deployed to production and
smoke-tested the same day (`docs/ops/deploy-log.md`). `DELIVERED` status remains defined
but unset by any of the three providers, unchanged from the note above — SMTP, like
WhatsApp/Telegram, has no delivery-receipt API to confirm it. **Not yet end-to-end
testable:** real `SMTP_*` credentials are still the Director's to supply (Decision 1's
two-step flow, same as the Anthropic API key) — until then, every real email send fails
fast with a clean `failed` status rather than doing anything, which is itself correct,
expected behaviour, not a bug.

**Decision 1 resolved 19 September 2026:** Director supplied real Google Workspace SMTP
credentials for `info@nestaprime.com` (an app password, generated after confirming
2-Step Verification was already on for that account). First attempt failed with a clean
`535 Username and Password not accepted` from Google — diagnosed as a copy-paste issue
with the app password itself, not a Workspace admin restriction (checked the Workspace
Admin Console's 2-Step Verification settings first, found nothing blocking); a freshly
regenerated app password, entered with an added length check (16 characters, matching
expected), authenticated successfully on the second attempt. Verified with a real send
from inside the production container straight to `info@nestaprime.com`, confirmed
landed in the Inbox (not spam) with the correct sender, subject, and body. Amendment 8
is now fully closed, end to end — email joins WhatsApp and Telegram as a genuinely live
send channel in production, not just correctly-coded-but-unconfigured.

### Amendment No. 9 — Flexible Court Sizing
Standard sizes become configurable suggestions per sport — adjustable smaller/larger per
project; admin-editable (links to No. 5).

**Implemented 12 September 2026 (PR #24):** `SportSelection.jsx`'s `CourtSize` accepts
the standard size with one click or reveals L/W inputs via "Customize size," floored
server-side at federation playing dimensions. **Nuance:** per-project override is
confirmed; a separate Master Settings control letting the Director edit the *baseline*
standard suggestion itself (as opposed to a project's override of it) wasn't found.

**Correction, 19 September 2026 (re-checked against current code, not assumed from
this entry's own older text):** that control already exists, and always has --
`backend/app/api/sports.py`'s `SportUpdate`/`update_sport()` (Director-only) already
accept and persist `playing_l_ft`/`playing_w_ft`/`build_l_ft`/`build_w_ft`, the actual
baseline dimensions, via `PATCH /sports/{id}`; `SportsScopeAdmin.jsx`'s Sports tab
already has editable fields for exactly this. `git log -S` traces it to `ff9e485`, the
*original* Sports & Scope Admin build -- it predates this amendment's own 12 September
review, which simply missed it (it lives on the Sports tab of Sports & Scope Admin, not
literally inside the Master Settings screen, which is where the review looked). No gap,
no code change needed. Amendment 9 is fully implemented.

### Amendment No. 10 — User Handbook (Guide for the Team)
**Why (Director)**: "One of the most important things" — a handbook the team can learn
from without calling the boss.

**Contents**:
1. One-page QUICK START card (the 5-step daily path, printable, kept at each desk).
2. Full handbook: every screen explained in plain business language with screenshots —
   what each field means, what to fill when the client hasn't provided data, and worked
   examples from real projects (e.g. the Ujjain Pickleball job).
3. Separate short sections per role: Estimator guide and Director/Admin guide (users,
   rates, reports).
4. FAQ: the twenty questions the team will actually ask (password reset, what to do when
   a quotation is rejected, how to revise, etc.).

**Language & format**: Simple English with Hindi terms where the team uses them
(estimators think in "labour, material, dhanda" — the handbook should speak that
language). PDF + printable; also lives inside the app under a "Help" button.

**Maintenance**: Handbook version-numbered; every shipped amendment wave updates the
relevant chapter (same discipline as this annexure).

**Partially implemented 12–13 September 2026 (PR #27 Quick Start, PR #34 full handbook
v2):** `Help.jsx` + `handbookData.js` deliver the Quick Start card, a 12-screen full
handbook, separate Estimator/Director guides, and an FAQ with exactly the spec'd 20
questions, reachable via an in-app Help button, with a browser print/save-as-PDF
option. **Gaps found in this reconciliation pass:** (1) Hindi terms are entirely
absent, despite the spec explicitly calling for them; (2) the maintenance rule this
amendment itself sets — "every shipped amendment wave updates the relevant chapter" —
has not been followed since PR #34: Amendments 11, 12, and 13 (14–16 September) all
shipped without any handbook update, so the handbook's 12-screen list is now missing
All Quotations, Vendors Admin, Messages Panel, Price Requests, Purchase Orders, and
Cross-Sell Admin. Bringing the handbook current is real, undone work — not a
documentation-only fix like the rest of this reconciliation pass.

**Closed (mostly) 16 September 2026 — handbook v3, undated in this register at the
time it shipped:** `handbookData.js`'s own changelog (not this register) records a v3
pass that closed both gaps above: All Projects, All Estimates, All Quotations, Vendors
Admin, Price Requests, Cross-Sell Admin, and Sports & Scope Admin were all added as
chapters (19 total, not 12); Hindi/Hinglish terms (*mazdoori*, *saaman*, *dhanda*) are
now woven through the Quick Start card, the full handbook, and the Estimator guide. An
undated 18 September touch-up also updated the Master Settings chapter for Section
14's Company Details/T&C editor. This register entry was never updated to reflect
either pass — corrected now, 18 September 2026, on re-verification against the actual
code rather than trusting this entry's own older text (same discipline used for
Amendments 4, 8, and 16 earlier today).

**Verified 18 September 2026 — what's actually still open, now that the above is
corrected:** three genuinely undocumented chapters (Education's Chat assistant and
Sport Build Guide, Amendment 15; the Build Guide's Construction Sequence section,
Section 18) and three now-stale passages describing pre-fix behavior (Documents
chapter still claims email "delivers nothing," superseded by Section 17; the Clients
chapter and FAQ Q18 both still describe the per-client project list as missing,
superseded by Section 19). Spec for closing these: `docs/annexures/Section-20-specs.md`.

**Implemented 18 September 2026 (PR #99, deployed to production same day -- see
`docs/ops/deploy-log.md`):** added the Education chapter (both tabs, including
Construction Sequence and its disclaimer); fixed the three stale passages (Documents,
Clients, FAQ Q18); folded in the Sports & Scope Admin Construction Sequence mention and
the Help.jsx version-label fix (both bumped 3->4). Direct content authorship, no
AI-draft step, per the approved spec. Amendment 10 is now current through Section 19 --
Simple Calculator, Tender Mode, and Amendment 11/14's smaller content gaps remain
explicitly out of scope, on record rather than forgotten.

### Amendment No. 11 — Rate Card & Margin Policy Tuning (from Note R1's Findings)
**Registered 14 September 2026.** Note R1's own completed exercise (see its "Completed
14 September 2026 — recreate & compare" entry below) produced three concrete,
evidence-backed candidates for tuning, each still parked behind Annexure 2's own Change
Process ("any resulting tuning ... needs its own Director-approved spec before
implementation"): (1) the three rate-table gaps (asphalt base, acrylic/PU court coating,
basketball pole+board) reconfirmed by two independent data sources; (2) five
labour-category % assumptions checked against one real project's actual material/labour
split; (3) the flat 15% Government-competitive margin target diverging sharply from two
real projects' actual achieved margins (11.0% and 22.9%).

**Implemented 14 September 2026 (Parts A & B1):** per the Director-approved
[Section-10-specs.md](Section-10-specs.md), `RateItem.rate` is now nullable -- the three
parked items (asphalt base, acrylic/PU court coating, basketball pole+board) are seeded
as real, HSN/SAC-classified catalog rows with `rate=null` ("awaiting rate"), visible on
the Rate Sheet but not confirmable into an AI rate until a PM/Director enters a real,
quantity-backed number. A new "Equipment installation (pre-fab)" labour category (8%
default) was split out of "MS fabrication & erection" (22%) for the genuine
6.4%-real-vs-22%-assumed gap found on Mathura's basketball pole installation. **Parts B2
and C were Director decisions, not code changes:** the other four labour-category %
assumptions are flagged for validation against future Note R1 project rebuilds rather
than moved off a single data point, and the flat 15% Government-competitive margin
target stays unchanged (Mathura's 2022 price is treated as historically underpriced, not
evidence the policy is wrong).

### Amendment No. 12 — Dashboard Drill-Down & Navigation Restructure
**Registered 15 September 2026 (Director instruction, real-usage feedback).** Two
confirmed problems with the current Dashboard/nav: (1) the Dashboard's summary tiles
(Open Projects, Pending Estimates, Pending Quotations) are static numbers with no
drill-through -- there is no screen anywhere in the app to browse the full list behind
any of them, only a short "Recent projects" list; (2) the Director's top nav carries 10
flat items, more than are used day to day. Director supplied a target navigation
structure (grouped: Dashboard / Quotation / Projects / Client / Vendor / Tools / Reports
/ Admin) to replace both. Spec: `docs/annexures/Section-11-specs.md`.

**Implemented 15 September 2026** (PR #57, deployed to production same day -- see
`docs/ops/deploy-log.md`): new All Projects / All Estimates screens; `status_group`
presets on the existing All Quotations screen; every Dashboard tile now drills through
to the right filtered screen; nav regrouped into Dashboard / Quotation / Projects /
Client / Vendor / Tools / Reports / Admin / Education dropdown menus; standalone "+ Add
Client" form; basic calculator under Tools; Education placeholder screen; hover motion
extended to Dashboard tiles, list rows, and nav items.

### Amendment No. 13 — AI-Assisted Content (Quotation Narrative, Client Messages, Report Summaries)
**Registered 15 September 2026 (Director instruction).** Following Amendment 12:
*"after that we will work on result meaning quotation format, and content, messages,
reports etc. idea is maximum utilization of AI in content side."* Director confirmed the
scope covers all three areas (quotation content, client messages, report summaries) and
that AI-drafted content must always be human-reviewed before it is sent or saved as
final -- no auto-send. Spec: `docs/annexures/Section-12-specs.md`.

**Implemented 16 September 2026** (PRs #59-#62, four small PRs per the approved build
order, each squash-merged after a green CI run): new `app/services/ai_content.py`
(Anthropic/Claude client, same blank-key-fails-fast discipline as wa_gateway.py/
telegram.py -- `ANTHROPIC_API_KEY` unset in every environment so far, including
production, so every "Draft with AI" / "Generate summary" button currently reports
"not configured" rather than doing anything, which is itself the graceful-degradation
behaviour Decision A called for); optional AI-draftable `Quotation.cover_note`,
rendered in the PDF only when set (#60); a "Draft with AI" button pre-filling the
existing Messages note field, no new send path (#61); an on-demand, never-persisted
"Generate summary" over each report's own already-computed content, inheriting that
report's own role gate (#62). Not yet deployed to production -- awaiting a Director-
supplied Anthropic API key (Decision A) before there's anything live to smoke-test.

**Update 16-17 September 2026:** Decision A resolved (real key configured and verified
on production, PR #65). Two follow-on refinements shipped after this entry was written:
a pinned Reports shortcut on the Dashboard (PR #66) and the Reports screen's raw JSON
debug view replaced with real Excel/PDF export plus the AI summary button (PR #68) --
Director instruction: *"in this no need to show backend process and report in excel or
pdf form only,"* then *"add pdf also."* See `docs/ops/deploy-log.md` for both deploys.

### Amendment No. 14 — Customizable Document Templates (Quotation, Estimate, Reports)
**Registered 17 September 2026 (Director instruction, following up on Amendment 13).**
Director asked whether the Quotation/Report/Cost Sheet PDFs could be changed to match
the company's actual real-world quotation format -- shared three real samples (a facility
layout diagram, and two branded "Budgetary/Technical Quotation" documents with a company
header, Project/Client Details, Scope of Work and Technical Specification tables, an
Approved Brands & Makes table, Payment/Commercial terms, Exclusions, and signed-off
blocks) -- *"why i am asking this because in present scenario we send quotation with
image for more clarity attached some samples."* Narrowed on follow-up to the concrete,
immediate pain point -- *"forget about content we need image attach in quotation or u
give me space for that i can attach things in quotation"* -- which shipped directly as
its own small feature (PR #75/#76, Quotation PDFs now embed any photo-tagged attachment
under a "Reference Images" heading). This amendment covers the remaining, broader ask:
letting the Director edit the PDFs' company details and boilerplate legal text from a
settings screen, without a developer, for future wording changes. Spec:
`docs/annexures/Section-14-specs.md`.

**Implemented 17 September 2026** (PR #78, deployed to production same day -- see
`docs/ops/deploy-log.md`): Master Settings gained a "Company details" panel (labeled
form over the 8 company-identity keys that already fed the Quotation PDF) and a
"Quotation terms & warranty" editor -- the 8 T&C clauses and 5-row warranty table,
previously hardcoded Python strings with no settings path, are now Director-editable
with a live preview against a real Quotation before saving. Scope stayed Quotation-only
and Tiers 1-2 only, per the approved spec's resolved open decisions; full layout/color/
font control (Tier 3) remains an explicitly out-of-scope possible future wave.

### Amendment No. 15 — Education Tab AI Assistant
**Registered 18 September 2026 (Director instruction).** Amendment 12 reserved an
"Education" nav slot ("Coming soon" placeholder) with no content ever specified beyond
the original ask to "describe... which points cover in education part." Director asked
*"can we connect any agent like chatgpt in this app in education tab"* -- clarified that
this should reuse the app's own existing Anthropic integration (Amendment 13's
`app/services/ai_content.py`, already powering Cover Notes, message drafts, and report
summaries) rather than adding a separate ChatGPT/OpenAI connection: *"no ChatGPT --
draft the Education assistant spec."* Spec: `docs/annexures/Section-15-specs.md`.

**Implemented 18 September 2026** (PR #83, deployed to production same day -- see
`docs/ops/deploy-log.md`): `ai_content.generate_chat_reply()` (a small additive,
multi-turn extension alongside the existing single-turn `generate_text`), `POST
/education/ask` (open to every role, matching Education's own nav visibility), and
`Education.jsx` as a real chat panel grounded only in the handbook -- no live app data.
Verified live on production: a real question about badminton federation dimensions
correctly triggered "I don't know, check Sport Selection" rather than inventing a
number, confirming the no-guessing guardrail works as designed.

### Amendment No. 16 — Sport Build Guide (Education)
**Registered 18 September 2026 (Director instruction, following up live-testing
Amendment 15).** Director's own scenario: *"my new sales person is completely clueless
for how to create quotation... [if a] customer says we want one basketball court for
school but other information not with sales person... what things need for basketball
court creation at scratch to ready to play base, flooring, lighting, pole, ring... this
is the hand holding for sales person to increases his efficiency and decrease the
error."* Checking the app's own data first (not guessed): a real, Director-verified,
per-sport build reference already exists across four tables that already drive real
Cost Sheets -- `Sport` (dimensions, indoor/outdoor -- confirmed `basketball_indoor` and
`basketball_outdoor` are already separate catalog rows, exactly the "two separate lists"
split asked for), `AccessoryCatalogItem` (item + qty per sport), `FlooringGuide`
(primary/secondary/budget spec + rationale per sport), `PackageContent`
(structure/lighting description per sport x tier), plus `GET /lighting-standards/lux`
and `/pole-counts`. None of it reaches Education today. Director confirmed: build the
structured "Build Guide" screen first, assembled from this existing verified data (no
new content authored); step-by-step construction *sequence* (the order things are
physically built) is real, separate, new content that doesn't exist anywhere in the app
yet, and is deferred to a later wave rather than invented now. Spec:
`docs/annexures/Section-16-specs.md`.

**Implemented 18 September 2026 (Part 1 only, PR #86, deployed to production same day --
see `docs/ops/deploy-log.md`):** `SportBuildGuide.jsx` assembles the real, already-verified
per-sport accessory/flooring/package-tier data that already drives real Cost Sheets -- no
new content authored, no new backend endpoints. Confirmed live: `basketball_indoor`/
`basketball_outdoor` are genuinely separate catalog entries, and a follow-up chat question
about flooring gave an answer that exactly matched the Build Guide's own data for that
sport. Part 2 (construction sequence) remained deferred as planned.

**Continued 18 September 2026 (Director instruction):** *"build the construction sequence
for the Sport Build Guide."* Spec for Part 2, named above: `docs/annexures/
Section-18-specs.md`.

**Implemented 18 September 2026 (Part 2, PR #93, deployed to production same day -- see
`docs/ops/deploy-log.md`):** new `ConstructionSequenceStep` table, one row per sport x
fixed phase (site prep, sub-base, flooring, structure/fixtures, lighting,
accessories/finishing), authored via the same AI-draft-then-Director-review pattern as
Amendment 13's Cover Notes -- drafting never persists, only an explicit Director save
does. Build Guide screen gained a Construction Sequence section (standing safety
disclaimer, shown only for sports with saved steps); Education chat's grounding extends
automatically through the existing client-side data assembly. Live-verified with a real
Anthropic call: drafted, saved, and cross-checked badminton's sequence against the Build
Guide display and the chat assistant's own answer -- all three agreed, disclaimer
included. Amendment 16 (both parts) is now fully closed.

### Amendment No. 17 — Export Output Sanitization (CSV/XLSX Formula Injection)
**Registered 19 September 2026 (self-identified during a Director-requested proactive
gap audit of the codebase against this register, then spot-verified against the live
code before recording).** Cost Sheet, Quotation, and other Excel/CSV exports write
free-text fields that any Sales/PM/Site Engineer user controls -- `CostSheetLine.item_name`/
`category`/`spec` and `Client.name` among them -- straight into exported cells with no
escaping of a leading `=`, `+`, `-`, or `@`. A line item or client deliberately named to
look like a formula would execute when the file is opened in Excel by a Director or
accountant outside the app -- a real trust-boundary gap (user input flowing into a file
consumed elsewhere), not a design choice. Evidence: `backend/app/api/exports.py:79-90`
(Cost Sheet export appends `line.item_name`/`category`/`spec` with no sanitization,
confirmed by direct read), `backend/app/api/quotations_admin.py:161-179`, and the same
`openpyxl`/`csv` pattern recurs across the consumption-sheet and other export endpoints
in `exports.py`/`reports.py`. Needs a Director-approved spec before implementation, per
this register's own Change Process.

**Implemented 19 September 2026 (PR #112, deployed to production same day -- see
`docs/ops/deploy-log.md`):** `app/core/export_safety.py::sanitize_row`, applied at all
ten identified `openpyxl`/`csv` write sites across `exports.py`, `quotations_admin.py`,
`rate_items.py`, `reports.py`, `settings.py`, and `audit_log.py`. A value starting with
`=`, `+`, `-`, or `@` gets a leading apostrophe at export time only -- storage and every
other display of the value are unaffected, and the app's own live formulas (Amount =
Quantity x Rate, etc.) are untouched since they're set separately, never through the
sanitized row. Live-verified in production: a real Cost Sheet line posted with
`category`/`item_name`/`spec` all crafted as formula-injection payloads came back
correctly neutralized in the exported XLSX, while the sheet's own live Amount formula
kept working. Amendment 17 is now fully closed.

### Amendment No. 18 — Login Rate Limiting / Lockout
**Registered 19 September 2026 (self-identified during the same audit).**
`POST /auth/login` (`backend/app/api/auth.py:35-50`) has no attempt counter, delay, or
lockout on repeated failed password checks -- unlimited guesses are possible against any
known email address. Confirmed by direct read that nothing else in this repo (no
middleware, no reverse-proxy config checked into the repo) covers this. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 19 September 2026 (PR #113, deployed to production same day -- see
`docs/ops/deploy-log.md`):** new migration adds `failed_login_attempts`/`locked_until`
to `User`, persisted on the row rather than kept in worker memory (production runs 2
gunicorn workers). 5 consecutive failed attempts against one account lock it for 15
minutes; every failure (unknown email, wrong password, locked account) returns the same
generic 401 so a client can't distinguish the cause. Unknown emails never count toward
any account's lockout, closing an email-guessing denial-of-service angle against real
accounts. A successful login resets both fields. Live-verified in production: 5
deliberate failed logins against a real account each returned 401, and critically a 6th
attempt with the *correct* password also returned 401 -- the account was genuinely
locked, not just rejecting bad guesses. Amendment 18 is now fully closed.

### Amendment No. 19 — Structure Form Crash on an Unrecognized Recommendation
**Registered 19 September 2026 (self-identified during a second Director-requested
proactive gap audit, spot-verified against the live code before recording).**
`frontend/src/CostSheetBuilder.jsx`'s Structure take-off form derives
`recStructureType = rec && mapStructureType(rec.structure_type)`, which is `null`
whenever E.4's recommended structure type doesn't match the parser. The "Use
recommendation" button's enabled condition checks `!recIsVendorQuoteOnly` (line 462),
and `recIsVendorQuoteOnly = recStructureType && [...]` is itself `null` (falsy) in that
same case -- so `!null` evaluates `true` and the button renders active with no warning,
instead of the sibling `BaseForm`'s correct pattern of gating directly on its own
`recBaseType`. Clicking it runs `useRecommendation()` (lines 412-420), which reads
`recStructureType.type` on a `null` value -- confirmed by direct read to throw
`TypeError: Cannot read properties of null (reading 'type')`, crashing the form for
whichever PM/Director hit it. Needs a Director-approved spec before implementation, per
this register's own Change Process.

**Implemented 19 September 2026 (PR #117, deployed to production same day -- see
`docs/ops/deploy-log.md`):** `onUse` now gates directly on `recStructureType`, matching
`BaseForm`'s already-correct pattern; a new "type not recognised -- pick manually" note
covers the case the old code silently mishandled; `useRecommendation()` also gained a
defensive early return as a second layer. Verified via clean production build and no
console errors on the live frontend after deploy -- the exact trigger condition isn't
reachable through normal seeded data, so this is confirmed by direct code trace of the
fix rather than a live repro. Amendment 19 is now fully closed.

### Amendment No. 20 — Purchase Order Receiving Overwrites Instead of Reconciling
**Registered 19 September 2026 (self-identified during the same audit).**
`backend/app/api/purchase_orders.py:287` (`receive_purchase_order`) does
`line.received_qty = update.received_qty` -- confirmed by direct read to be a plain
overwrite, not additive, with no row lock or version check. Two staff independently
recording separate partial deliveries close together (e.g. from separate paper delivery
notes) can have the second commit silently clobber the first's recorded receipt, with no
conflict signal to either party -- a real lost-update risk on inventory data the
Consumption Sheet and BOM both depend on. A related, smaller correctness gap in the same
function: `po.status` (lines 289-292) has `RECEIVED`/`PARTIALLY_RECEIVED` branches but no
`else`, so correcting a line's `received_qty` back down to 0 leaves `status` stuck at
`PARTIALLY_RECEIVED` instead of reverting to `ISSUED`, contradicting the function's own
docstring ("status derives from the lines' own received_qty vs quantity"). Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 19 September 2026 (PR #118, deployed to production same day -- see
`docs/ops/deploy-log.md`):** `ReceiveLineIn` gained an optional `expected_received_qty`;
a mismatch against the line's current value now returns `409` instead of overwriting,
and `PurchaseOrdersPanel.jsx` sends what it last displayed and re-fetches on any receive
error. The missing `else` branch was added so `po.status` reverts to `issued` when every
line's `received_qty` is corrected back to 0. Live-verified end to end in production: a
real PO's first receipt (200 units) succeeded; a second receipt still asserting the old
value was rejected with `409` and the first receipt's 200 units were confirmed intact
afterward; correcting back to 0 with the right expected value reverted status to
`issued`. Amendment 20 is now fully closed.

### Amendment No. 21 — No Double-Submit Guard on Cost Sheet Take-Off Forms
**Registered 19 September 2026 (self-identified during the same audit).**
`frontend/src/CostSheetBuilder.jsx` contains 21 separate `async function submit` take-off
handlers (Structure, Manual Line, Flooring, Lighting, HVAC, Athletics, and every other
per-category form) -- confirmed by direct grep that none of them track a `submitting`
flag or disable their submit button during the `await`, unlike this app's own established
pattern elsewhere (`AttachmentsPanel.jsx`, `RateSheet.jsx`, `ProjectSetup.jsx` all guard
against this). A double-click on any "Compute & add to Cost Sheet" button fires two
identical POSTs before the first resolves, silently duplicating a cost-sheet line and
inflating `cost_total` -- a real risk on the screen this app's own pricing accuracy most
depends on. Needs a Director-approved spec before implementation, per this register's own
Change Process.

**Implemented 19 September 2026 (PR #119, deployed to production same day -- see
`docs/ops/deploy-log.md`):** all 21 take-off forms gained a local `saving` state, set on
submit and reset in a `finally`, with the submit button disabled while saving -- reusing
this codebase's own existing pattern rather than a new abstraction. This branch shared
`CostSheetBuilder.jsx` with PR #117 (Amendment 19); the rebase auto-merged cleanly and
both fixes were confirmed present together before pushing. Verified via clean production
build and no console errors on the live frontend after deploy. Amendment 21 is now fully
closed.

### Amendment No. 22 — Master Settings Override Values Are Never Validated
**Registered 19 September 2026 (self-identified during a third Director-requested
proactive gap audit against the register, spot-verified against the live code before
recording).** `OverrideCreate` (`backend/app/api/settings.py:376-382`) accepts
`setting_key: str` and `override_value: str` with no validation at all -- no check that
`setting_key` matches any real Setting, no numeric/range constraint on `override_value`,
confirmed by direct read of `create_override` (lines 398-416). The same gap exists one
layer up at `SettingCreate` (lines 133-139): a Master Setting's own `value: str` is
equally unvalidated at write time, unlike `bulk_update_settings` (lines 184-230), which
at least wraps its arithmetic in `try/except ValueError` and skips non-numeric rows
rather than persisting one. `_get_effective_setting_float`
(`backend/app/api/documents.py:255-265`) does `float(override.override_value)` with no
try/except, feeding directly into the Cost Sheet's core cost-build chain
(`site_establishment_percent`, `company_overhead_percent`, `contingency_percent`,
`documents.py:861-910`). A Director (or PM -- `OVERRIDE_ROLES = ("pm", "director")`)
entering a typo'd override doesn't fail at write time; it fails later, as an unhandled
`ValueError` -> 500, on every future computation of that document, since Overrides are
write-once/most-recent-wins with nothing to clean one up. A numerically valid but
out-of-range value (e.g. a `gst_rate_percent` override of `-100`) can also reach
`pricing.py:324`'s `1 + gst_rate_percent / 100` divisor and produce a
`ZeroDivisionError` instead of a rejected input. Needs a Director-approved spec before
implementation, per this register's own Change Process.

**Implemented 19 September 2026 (PR #123, deployed to production same day -- see
`docs/ops/deploy-log.md`):** new `app/core/settings_parse.py::parse_setting_number`
wraps every numeric parse of a stored Setting/Override value across `documents.py`,
`schedule.py`, `sports.py`, `settings.py`, and `pricing.py`, raising a clear
`HTTPException` naming the broken key instead of a bare crash; `pricing.py`'s GST
divisor is now guarded against a rate `<= -100`; `POST /overrides` rejects a non-numeric
`override_value` at write time when the Setting it replaces was itself numeric, leaving
genuinely text-valued Settings (company details, T&C clauses) unaffected. Live-verified
in production: a numeric-setting override with a non-numeric value was rejected with a
clear `422`, while a valid numeric override still succeeded. The GST-divisor guard
itself was deliberately not live-tested against the real global setting (too risky on a
live system) -- covered instead by `backend/tests/test_override_validation.py` against
the real `/pricing/quote` endpoint in the isolated test database. Amendment 22 is now
fully closed.

### Amendment No. 23 — Document/PO Number Generation Races Under Concurrent Creation
**Registered 19 September 2026 (self-identified during the same audit).**
`_generate_project_no` (`backend/app/api/projects.py:36-49`) and `_po_number`
(`backend/app/api/purchase_orders.py:27-33`) both compute the next sequence number via
a `SELECT`-then-compute-max-in-Python pattern, confirmed by direct read to have no row
lock (`with_for_update`) and no database sequence -- the only protection is each
column's `unique=True` constraint (`Project.project_no`, `PurchaseOrder.po_no`, both
confirmed present). Two PMs creating a project (or two POs on the same project) at the
same moment can both read the same existing-numbers set, both compute the identical
next number, and the second commit dies with an unhandled `IntegrityError` -> 500,
instead of a graceful retry or a real, distinct number. A narrow race window, but a
genuine availability gap for concurrent daily use by multiple PMs/Procurement staff.
Needs a Director-approved spec before implementation, per this register's own Change
Process.

**Implemented 19 September 2026 (PR #122, deployed to production same day -- see
`docs/ops/deploy-log.md`):** new `app/core/db_retry.py::create_with_retry` wraps the
build-and-commit for both `create_project` and `create_purchase_order` -- on a
unique-constraint collision it rolls back and calls `build()` again, which recomputes
the sequence number against the now-updated row set, rather than surfacing the
collision as a raw 500. No schema change, no dedicated sequence table, per the approved
spec's catch-and-retry decision. Since this codebase tests against a real Postgres
database (no mocks), the collision itself is tested by controlling what the `build()`
callable returns deterministically rather than faking concurrency --
`backend/tests/test_sequence_number_retry.py` confirms a real collision recovers on
retry with no zombie row left behind, and confirms the retry gives up cleanly after
exhausting its attempts. Live-verified in production: two projects created back to back
both succeeded with distinct, correctly sequential numbers -- the normal path is
unaffected. Amendment 23 is now fully closed.

### Amendment No. 24 — Quotation PDF and Billing Handoff Hardcode a False "18% Flat" GST Label
**Registered 20 September 2026 (self-identified during a fourth Director-requested
proactive gap audit against the register, spot-verified against the live code before
recording).** `backend/app/api/pdf_documents.py:841` prints the literal string
`"GST @ 18% (flat)"` next to the real, computed GST amount
(`format_inr(gst_amount)`); `backend/app/api/exports.py:288`'s Billing Handoff export
carries the identical hardcoded claim in its own row label
(`"Total (GST-inclusive, 18% flat)"`). Both are confirmed by direct read to be plain
string literals, not derived from the rate actually used. That rate is Director-
configurable (`get_gst_rate_percent`, `backend/app/api/settings.py`) and, per Note R1's
own shipped work, blends in a 5% rate for HSN-9506 sports-equipment lines when a Cost
Sheet mixes equipment with 18%-rated civil/flooring work
(`cost_weighted_gst_rate_percent`, `backend/app/api/pricing.py:256-274`). Whenever the
effective rate isn't literally a flat 18% -- a changed Master Setting, or any project
mixing equipment and civil-work lines, exactly the scenario Note R1 built -- the
client-facing Quotation PDF and the internal Billing Handoff both print a false rate
label next to a correctly-computed but differently-derived amount. Tax-compliance-
adjacent and reaches the client directly. Needs a Director-approved spec before
implementation, per this register's own Change Process.

**Implemented 20 September 2026 (PR #127, deployed to production same day -- see
`docs/ops/deploy-log.md`):** both labels now back-derive the effective rate from the
document's own frozen `gst_amount`/`selling_after_discount` (`gst_amount /
selling_after_discount * 100`, valid in both `GstMode.EXCLUSIVE` and `INCLUSIVE`) --
the only choice that stays consistent with the rupee amount already printed next to it,
rather than re-querying a Master Setting that could have changed since. "(flat)"/"flat"
dropped from both labels. Live-verified in production: a real Quotation's PDF (via
`pypdf`'s actual text extraction) shows "GST @ 18.0%" with no "(flat)" text, and its
Billing Handoff export shows "Total (GST-inclusive, 18.0%)". Amendment 24 is now fully
closed.

### Amendment No. 25 — Rate Sheet Excel Import Silently Discards Non-Rate Field Edits
**Registered 20 September 2026 (self-identified during the same audit).**
`backend/app/api/rate_items.py:772-795` (`import_rate_items`): the `if rate is not None
and rate != previous_rate:` branch is confirmed by direct read to be the *only* place
that applies `unit`/`hsn_sac`/`vendor`/`city_of_quote`/`labour_category_id`/
`is_commodity_watched` changes from an imported row -- the `else` branch (line 795)
just increments `unchanged` and applies none of those fields, even when they genuinely
differ from the file. The function's own docstring (lines 670-696) states "other
changed fields ... are applied directly, same as PATCH .../{id}", which is only true
when the rate also changed. A PM/Director bulk-correcting vendor names, HSN/SAC codes,
or the commodity-watch flag via Excel -- with rates left untouched, a plausible and
likely common editing pattern -- has every one of those edits silently dropped, and the
import result reports the row as "unchanged," giving false confidence the import
succeeded. A real data-loss risk on a documented bulk-edit workflow. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 20 September 2026 (PR #128, deployed to production same day -- see
`docs/ops/deploy-log.md`):** decoupled `rate_changed` (still the only thing triggering
`RateHistory` versioning, unchanged) from `fields_changed` (now governs whether the
edit applies and the row counts as `updated`) -- a row where any field genuinely
differs now gets that edit applied and counts as updated, even with the Rate cell left
blank or numerically unchanged. Live-verified in production: imported an Excel row
changing only the vendor with Rate left blank -- the row came back as `updated`, the
vendor was applied, and the rate stayed untouched at its original value. Amendment 25
is now fully closed.

### Amendment No. 26 — Re-Creating an Estimate or Quotation for a Project Crashes (500)
**Registered 20 September 2026 (self-identified during a fifth Director-requested
proactive gap audit against the register, spot-verified against the live code before
recording).** `backend/app/api/documents.py`'s `create_estimate` (line 1452) and
`create_quotation` (lines 1943, 2114) all build `document_no` via
`_document_no(project.project_no, "EST"/"NPQ", 1)` -- confirmed by direct read to be a
**hardcoded revision `1`**, not derived from how many Estimates/Quotations the project
already has. Both `Estimate.document_no` and `Quotation.document_no` are `unique=True`
(`backend/app/models/document.py:240,354`), and neither `create_estimate` nor
`create_quotation` queries for an existing document on the project before inserting --
confirmed by direct read of `create_estimate`'s full body (lines 1405-1452), which has
no such check. The existing "revise" endpoints (`documents.py:1652`, `2305`) correctly
increment `old.revision_major + 1`, but those operate on an *existing* Estimate/
Quotation being revised -- they don't help a project that needs a brand-new document
chain (e.g. re-bidding a project whose earlier Quotation was marked Lost). The moment a
second Estimate is created for such a project, the second `document_no` collides with
the first and the request dies with an unhandled `IntegrityError` -> 500, not a clear
error -- and there is no supported way to restart a project's document chain at all.
Needs a Director-approved spec before implementation, per this register's own Change
Process.

**Implemented 20 September 2026 (PR #132, deployed to production same day, per
[docs/annexures/Section-32-specs.md](Section-32-specs.md), approved as proposed).** Adds
`_next_fresh_document_revision(db, model, project_id)`, computing `max(existing
revision_major) + 1` for the project -- same read-existing-then-compute-next shape
Amendment 23 already uses for `_generate_project_no`/`_po_number`. All four "fresh
document" creation sites (`create_estimate`; `create_quotation`'s normal path; both the
Estimate and Quotation created inside `create_fast_track_quotation`) now call this
instead of hardcoding `1`, with `revision_major` set explicitly on the constructed row
(not just embedded in the `document_no` string) to avoid an internal inconsistency
between the two. Cost Sheet's own `_document_no` sites were left untouched, out of
scope per the approved spec. Live-verified in production: re-bid a throwaway project
past a Lost Quotation -- a second Estimate and a second Quotation, created directly
(not via `/revise`), both succeeded with `201` and clean `R2` document numbers
(`EST-2609-0011-R2`, `NPQ-2609-0011-R2`) instead of the old unhandled 500. Amendment 26
is now fully closed.

### Amendment No. 27 — Vendor Price Request Replies Ignore the Parsed GST Basis
**Registered 20 September 2026 (self-identified during the same audit).**
`backend/app/api/price_requests.py:593` (`rate_item.rate = reply.parsed_rate`) and
`:618` (`line.rate = reply.parsed_rate`), inside `use_vendor_reply`, both apply the
vendor's parsed rate literally to the Rate Master / Cost Sheet line. `VendorReply.
parsed_gst_basis` (`EXCLUSIVE`/`INCLUSIVE`, parsed from the vendor's free-text reply,
`price_requests.py:79-93`) is captured, stored (`models/price_request.py:123`), and
returned in `VendorReplyOut` (`price_requests.py:230,253`) -- but confirmed by direct
read and grep to be **never referenced anywhere inside `use_vendor_reply`**. A vendor
who replies "Rs 100/kg incl. GST" has that rupee-100 figure written straight into
`RateItem.rate`/`CostSheetLine.rate` as if it were the ex-GST material rate the pricing
engine expects everywhere else -- silently overstating the cost basis by the embedded
GST% on every downstream Cost Sheet/Estimate/Quotation that uses that rate, with no
error or warning surfaced anywhere. A closely related gap in the same function
(`price_requests.py:608-619`): the `COST_SHEET_LINE`/`BOTH` branch takes an arbitrary
`cost_sheet_line_id` from the request payload with no check that the targeted line
actually corresponds to the `PriceRequestItem` the reply answers, so a reply can be
misapplied onto an unrelated cost-sheet line with no server-side guard catching it.
Needs a Director-approved spec before implementation, per this register's own Change
Process.

**Implemented 20 September 2026 (PR #134, deployed to production same day, per
[docs/annexures/Section-33-specs.md](Section-33-specs.md), approved as proposed).** An
`INCLUSIVE` reply is now converted via `ex_gst_rate = parsed_rate / (1 +
applicable_gst_percent / 100)` before being applied anywhere, where
`applicable_gst_percent` is the rate item's own `gst_percent` override if set, else the
global Master Setting -- the same item-override-else-global resolution order
`pricing.py`'s own `_line_gst_percent` already uses. An `EXCLUSIVE` reply applies
unchanged. A reply whose basis couldn't be parsed now requires the caller to pass
`confirmed_ex_gst=true`, rejecting with `422` naming the ambiguity otherwise, rather than
silently assuming exclusive. Also adds the missing cross-check: applying a reply to a
Cost Sheet line whose `rate_item_id` doesn't match the price request item it answers is
now rejected with `400`. Live-verified in production: a vendor reply of "Rs 118/kg incl
GST" (against the live 18% global setting) correctly applied a `100.0` ex-GST rate to the
Rate Master, and a reply with no parseable GST wording was correctly rejected with `422`
until confirmed. Amendment 27 is now fully closed.

### Amendment No. 28 — Dashboard "Open Projects" Permanently Misclassifies Restarted Projects
**Registered 20 September 2026 (self-identified during the same audit).**
`backend/app/api/dashboard.py:62-70`: `closed_project_ids` is every `project_id` where
*any* Quotation has ever reached `WON`/`LOST` status, and `open_projects_count` excludes
every one of those projects entirely -- confirmed by direct read. Nothing in
`create_estimate`/`create_quotation` prevents a fresh Estimate/Quotation cycle from
starting on a project after an earlier one was marked Lost (aside from the unrelated
crash Amendment 26 covers) -- but even once that crash is fixed, a project with any
historical WON/LOST quotation stays excluded from the "Open Projects" tile forever,
even if a brand-new, currently-active Quotation now exists for it. Real, active work is
silently dropped from the number a Director checks daily. A related, broader gap in the
same function: dashboard tiles (`open_projects_count`, `pending_estimates_count`,
`pending_quotations_count`) have no calibration/test-project exclusion filter at all --
confirmed by a repo-wide grep for `is_calibration`/`is_test`/`calibration` across
`backend/app/models` and `backend/app/api` returning zero matches, despite this
register's own Amendment 4 refinement text explicitly calling for one ("so real client
work isn't crowded by validation data") and Note R1's Mathura/Noida/Bathinda projects
being real, recreated-end-to-end database rows that would count toward these tiles
indistinguishably from genuine client work. Needs a Director-approved spec before
implementation, per this register's own Change Process.

**Implemented 20 September 2026 (PR #136, deployed to production same day, per
[docs/annexures/Section-34-specs.md](Section-34-specs.md), approved as proposed).** Part
A: `closed_project_ids` now derives from projects with no live (non-Won/Lost) Quotation,
so only a project where *every* Quotation is closed counts as closed; a project with zero
Quotations is still never closed, unaffected. Part B: a new `Project.is_calibration`
boolean column (migration `323ecc35b9df`, default `False`), settable on `ProjectCreate`
(same role gate as project creation) or via a new Director-only `PATCH
/projects/{id}/calibration`; all three dashboard tiles now exclude flagged projects.
Live-verified in production: a project re-bid past a Lost quotation correctly returned to
Open (11 -> 10 -> 11 on the live counter); a calibration-flagged project was excluded from
both `open_projects_count` and `pending_estimates_count`; the Director-only PATCH backfill
mechanism worked end-to-end. **Backfill note:** the Mathura/Noida/Bathinda projects this
paragraph's registered text refers to do not exist as rows on the production server (a
direct DB search by city/client-name/notes across all 15 production projects found zero
matches) -- whatever environment that recreation work was done in, it was never persisted
here. The production server's actual calibration data was instead two projects under
client "Pathankot Badminton Court (FY23-24 actual, calibration)" (`P-2609-0002`,
`P-2609-0003`) -- self-identified by name -- which have now been flagged
`is_calibration=True` via the new PATCH endpoint. Amendment 28 is now fully closed.

### Amendment No. 29 — Director Can Silently Flip a Client's Blacklist/Overdue Flags With No Audit Trail
**Registered 21 September 2026 (self-identified during a sixth Director-requested
proactive gap audit against the register, spot-verified against the live code before
recording).** `backend/app/api/clients.py:165-186` (`update_client_flags`, the
Director-only `PATCH /clients/{client_id}` that sets `overdue_flag`/`blacklist_flag`)
calls `db.commit()` directly with no `write_audit_log_entry` call and no `request`
parameter at all -- confirmed by direct read. These two flags are not cosmetic:
`blacklist_flag` blocks new Estimate creation (`documents.py:1459`, `:2096`) and
`overdue_flag` blocks Quotation release (`documents.py:2465`) -- Part O's own stated
purpose for both. The very next function in the same file, `update_client_consent`
(`clients.py:189-219`), does the correct thing: it takes a `request` parameter and calls
`write_audit_log_entry` for every changed field. A Director can silently blacklist or
un-blacklist a client (or clear/set overdue) with zero record of who did it or when, on a
control whose entire purpose is Director-level financial gatekeeping. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 21 September 2026 (PR #140, deployed to production same day, per
[docs/annexures/Section-35-specs.md](Section-35-specs.md), approved as proposed).**
`update_client_flags` now takes a `request` parameter and mirrors
`update_client_consent`'s own changed-field logging loop exactly, reusing
`document_type="client"` so both consent and flag history live in the same per-client
audit trail. Live-verified in production: setting `blacklist_flag` to `True` on a
throwaway client wrote a `client` audit entry (`False` -> `True`). Amendment 29 is now
fully closed.

### Amendment No. 30 — Report Release Has No Audit Trail, Unlike the Identical Quotation-Release Pattern
**Registered 21 September 2026 (self-identified during the same audit).**
`backend/app/api/reports.py:647-665` (`release_report`, Director-only, DRAFT ->
RELEASED) never imports or calls `write_audit_log_entry` -- confirmed by a grep of the
entire file returning zero matches for either. The exactly analogous status-transition
endpoint elsewhere in the codebase, `release_quotation`
(`backend/app/api/documents.py:2443-2498`), does log the transition. Margin/Override
Summary reports carry cost/margin and override-frequency data restricted to PM/Director
(`VISIBLE_ROLES`) -- releasing one is a governance action with no record beyond the row's
own `released_by_id`/`released_at`, which isn't surfaced anywhere the audit log is. Needs
a Director-approved spec before implementation, per this register's own Change Process.

**Implemented 21 September 2026 (PR #141, deployed to production same day, per
[docs/annexures/Section-36-specs.md](Section-36-specs.md), approved as proposed).**
`release_report` now logs its DRAFT -> RELEASED transition unconditionally (every
release here is already Director-only, unlike `release_quotation`'s conditional
PM-vs-Director split), under `document_type="report"`. Live-verified in production:
releasing a Margin report wrote a `report` audit entry (`draft` -> `released`).
Amendment 30 is now fully closed.

### Amendment No. 31 — Client Signatory Records Have No Audit Trail At All
**Registered 21 September 2026 (self-identified during the same audit).**
`backend/app/api/client_signatories.py` -- the entire file -- has no
`write_audit_log_entry` import or call anywhere, confirmed by grep returning zero
matches. `create_signatory` and `update_signatory` let Sales/PM/Director create, edit,
deactivate, or **reactivate** a `ClientSignatory` with zero trail. This matters because
`attachments.py`'s `_match_active_signatory` (`attachments.py:132-149`) uses these exact
rows to decide whether a client-side approval on an `approval_evidence` attachment is
considered legally valid -- someone could quietly extend an `expiry_date`, flip a
departed employee's `is_active` back to `True`, or edit a `designation` to make a stale
signatory match again, with no audit entry anywhere to catch it. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 21 September 2026 (PR #142, deployed to production same day, per
[docs/annexures/Section-37-specs.md](Section-37-specs.md), approved as proposed).**
`create_signatory` now logs a "created" entry; `update_signatory` logs one entry per
field that actually changed (all fields, not just `is_active`/`expiry_date`), both under
a new `document_type="client_signatory"` category kept separate from the parent client's
own `"client"` trail. Live-verified in production: creating a signatory wrote a
"created" entry naming it, and updating its `designation` and `is_active` wrote two
correctly-valued entries. Amendment 31 is now fully closed.

### Amendment No. 32 — Master Settings Override's Amendment-22 Numeric Guard Is Bypassable
**Registered 21 September 2026 (self-identified during a seventh Director-requested
proactive gap audit against the register, spot-verified against the live code before
recording).** `backend/app/api/settings.py:377-427` (`create_override`)'s Amendment 22
numeric-consistency check only inspects the caller-supplied `OverrideCreate.master_value`
field -- confirmed by direct read to never call `get_current_setting_value(db,
payload.setting_key)` to check what the real, current Master Setting value actually is.
A PM or Director (both in `OVERRIDE_ROLES`) can send a fabricated non-numeric
`master_value` for a `setting_key` that is genuinely numeric (e.g. `gst_rate_percent`),
which skips the `try: float(payload.master_value) except ValueError: pass` branch
entirely and lets a non-numeric `override_value` persist unchecked -- reopening the exact
deferred-failure risk Amendment 22 was built to close (the write-time guard is
defeatable; a later document computation now raises a clear `parse_setting_number`
`HTTPException` rather than a bare crash, so this is a smaller regression than the
original Amendment 22 gap, but the guard itself does not do what its own comment claims).
Separately, `create_override` also never checks that `setting_key` corresponds to a real
Setting row or that `document_id` corresponds to a real document of `document_type`.
Needs a Director-approved spec before implementation, per this register's own Change
Process.

**Implemented 21 September 2026 (PR #146, deployed to production 22 September 2026, per
[docs/annexures/Section-38-specs.md](Section-38-specs.md), approved as proposed -- with
one narrowing revision agreed during implementation).** `master_value` is removed from
`OverrideCreate`; the server now looks up the real value via `get_current_setting_value()`
and uses it for both the numeric check and the persisted `Override.master_value`. The
originally-approved "reject unknown `setting_key` with 404" behavior was dropped after
discovering, mid-implementation, that most K.1 cost-sheet constants run purely on a
hardcoded Python default with no `Settings` row ever created for them -- a normal,
legitimate case (confirmed by an existing, previously-passing test), not an unknown key;
requiring a row would have broken real overrides of those constants. When no row exists,
the numeric check is skipped exactly as before Amendment 32, with a placeholder value
recorded since there's nothing authoritative to check `override_value` against. This
revision was confirmed with the Director before proceeding. Live-verified in production: a
fabricated `master_value` sent alongside a real numeric setting was ignored and the
override correctly rejected (`422`) against the real value; a legitimate override against
that same real setting recorded the correct `master_value` (`6.0`); an override against a
key with no `Settings` row (confirmed via direct DB query before testing, to avoid the
false negative a pre-existing real row would cause) still succeeded with the new
placeholder `master_value` text. Amendment 32 is now fully closed.

### Amendment No. 33 — Skip Request Workflow Has No Reject Path, Can Deadlock a Project
**Registered 21 September 2026 (self-identified during the same audit).**
`backend/app/models/skip_request.py`'s `SkipRequestStatus` enum has only `PENDING` and
`APPROVED` members -- confirmed by direct read, no `REJECTED`/`DECLINED` value exists.
`backend/app/api/skip_requests.py` registers `create_skip_request`, `list_skip_requests`,
and `approve_skip_request` only -- confirmed by grep, no reject/decline endpoint exists
anywhere in the backend, and the frontend (`Documents.jsx`/`api.js`) only wires up
`approveSkipRequest`. `create_skip_request` (`skip_requests.py:72-78`) blocks creating a
second skip request while one is already `PENDING` for the project, so once a PM or
Director decides *not* to approve a Sales-raised skip request, there is no way to close
it out -- it sits `PENDING` forever, permanently blocking any future skip request on that
project, with no record anywhere that a decision was ever made. A normal, full Cost Sheet
build is unaffected by (and doesn't clear) a pending `SkipRequest` either, so the two
paths can silently diverge. Needs a Director-approved spec before implementation, per
this register's own Change Process.

**Implemented 21 September 2026 (PR #147, deployed to production 22 September 2026, per
[docs/annexures/Section-39-specs.md](Section-39-specs.md), approved as proposed).** Adds a
`REJECTED` status (migration `ac1785734f0f`, `ALTER TYPE ... ADD VALUE`) and a
`rejection_reason` column, a new `POST /skip-requests/{id}/reject` endpoint (same
PM/Director role gate as approve, audit-logged), and a symmetric guard on
`create_cost_sheet` rejecting while a skip request is pending. Live-verified in
production: a normal Cost Sheet build was correctly blocked (`400`) while a skip request
sat pending; rejecting it recorded `status: rejected` and the rejection reason; a second
skip request could then be raised on the same project (the deadlock resolved); the normal
Cost Sheet path was correctly blocked again by that second pending request. Amendment 33
is now fully closed.

### Amendment No. 34 — Vendor Master Has No Deactivation and No Duplicate-Vendor Guard
**Registered 21 September 2026 (self-identified during the same audit).**
`backend/app/models/vendor.py`'s `Vendor` model has no `is_active` column at all --
confirmed by a full model read and a grep for `is_active` returning zero matches --
unlike `Hub` (`backend/app/models/hub.py`), which explicitly documents following
"Sport/ScopeItem's own convention" for exactly this kind of retire-without-delete flag.
`backend/app/api/vendors.py` has no DELETE endpoint for a vendor either (only for a
vendor's `Product` rows) -- confirmed by grep of every route in the file -- so a vendor
can never be retired once created; it stays selectable in RFQ, Purchase Order, and Price
Request flows indefinitely, with no way to signal "we no longer use this vendor" short of
manually avoiding it. `create_vendor` (`vendors.py:80-90`) also performs zero duplicate
check on `name` or `gstin` before inserting -- confirmed by direct read (`vendor =
Vendor(**payload.model_dump()); db.add(vendor); db.commit()`, no prior query) -- unlike
`create_hub`'s explicit `409` on a duplicate name in the same codebase
(`hubs.py:61-62`). Needs a Director-approved spec before implementation, per this
register's own Change Process.

**Implemented 22 September 2026 (PR #149, deployed to production same day, per
[docs/annexures/Section-40-specs.md](Section-40-specs.md), approved as proposed).** Adds a
nullable-safe `Vendor.is_active` column (migration `9e8bdbaf6219`, default `True`) --
retirement is deactivation, not deletion, matching `Hub`/`ClientSignatory`'s existing
convention, since a vendor may be referenced by historical Price Requests/POs/RateHistory
rows. `list_vendors` gains `include_inactive` (same shape as `list_hubs`), and
`create_vendor` now `409`s on a duplicate `name` or a duplicate `gstin` when one is
given -- `gstin=None` legitimately means "unregistered," so multiple unregistered vendors
don't collide with each other. Live-verified in production: a new vendor defaulted to
`is_active: true`; a duplicate name and a duplicate GSTIN were both rejected with `409`;
deactivating a vendor removed it from the default listing while it remained retrievable
directly by id and via `include_inactive=true`. Amendment 34 is now fully closed --
**this closes out the entire seventh gap-audit batch (Amendments 32-34).**

### Amendment No. 35 — Site Survey Has No Forward Navigation, a Genuine Dead End for Sales
**Registered 22 September 2026** (from the Director's screenshot-reported UX complaints,
`docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md` Section A.4, confirmed by
direct read before registering). `frontend/src/SiteSurvey.jsx:190-194` has only a "←
Back" control -- no forward/Next button anywhere on the screen. `frontend/src/App.jsx:
488-495` mounts `<SiteSurvey onBack={...} />` without ever passing an `onNext` prop,
unlike `ScopeChecklist`, which receives `onNext`/`onDocuments`/`onSiteSurvey`
(`App.jsx:478-487`) and can therefore route the user onward. A Sales rep who finishes a
Site Survey and taps "Mark Completed" has no button to press next -- confirmed this is a
real functional dead end, not a cosmetic gap. Separately confirmed and ruled out during
the same investigation: the survey's fields are **not** all mandatory as originally
suspected -- only `photo_count >= 4` gates "Mark Completed"
(`backend/app/api/site_surveys.py:24`, `MIN_PHOTOS_TO_COMPLETE = 4`); every other field on
`SiteSurvey` (`backend/app/models/site_survey.py:53-77`) is already nullable. That part of
the original complaint does not need a code change. Needs a Director-approved spec before
implementation, per this register's own Change Process.

### Amendment No. 36 — Nav Shell + Dashboard Shell (CRM Restructure, Phase 1 of the Header Index)
**Registered 22 September 2026**, from
`docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md` Sections D/E (Director
decision to move to a CRM-shaped sidebar navigation, "shell-first" build order). Current
state: `frontend/src/App.jsx:129-213` renders a top nav with dropdown groups (Dashboard /
Quotation / Projects / Client / Vendor / Tools / Reports / Admin / Education);
`frontend/src/Dashboard.jsx` is 5 static tiles + a flat project list, confirmed by direct
read, no charts, no CRM-shaped data (Opportunities, Follow-ups, Payments-due all
confirmed absent from the schema, see `PROJECT-BLUEPRINT.md` Section 6). This is Phase 1
of the 9-step header-by-header build index in Section E of the plan doc: replaces the nav
shell with a left sidebar carrying every E.1-confirmed header (Overview, Leads & Clients,
Opportunities, Quotations, Projects, Payments, Follow-ups, Team & Access), and builds the
Overview/Dashboard's visual shell against the CRM reference layout, with honest empty/zero
states for every tile whose real data (Opportunities, Follow-ups, Payments-due) does not
exist yet -- no fake/sample numbers. Vendor/Tools/Reports/Admin/Education placement is
explicitly deferred to Phase 8 (Team & Access) per Director decision 2026-09-22; those
screens must remain reachable during this phase, not hidden or removed. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 22 September 2026 (PR #151, deployed to production same day, per
[docs/annexures/Section-42-specs.md](Section-42-specs.md), approved as proposed).** Adds
`frontend/src/Sidebar.jsx` (the new left sidebar, replacing `App.jsx`'s old `navGroups`
dropdown block) and `frontend/src/ComingSoon.jsx` (the honest placeholder for
Opportunities/Follow-ups/Payments); rewrites `Dashboard.jsx` as the "Overview" shell --
Pending Quotations and Active Projects tiles reuse the existing `/dashboard` endpoint
unchanged, the other three tiles and two panel placeholders show "Soon"/"Coming soon"
rather than a fabricated number. Vendor/Tools/Reports/Admin/Education re-homed into a
temporary "More" accordion with their exact old sub-groupings and role gates preserved.
No backend changes. All three open decisions closed as proposed (existing gold-accent
theme kept, plain-text empty states, old groupings preserved under "More").

**Live-verified in production:** `git pull` fast-forwarded cleanly, backend rebuild was a
clean no-op (no migration, as expected for a frontend-only change), frontend rebuild and
`nginx` publish succeeded, `curl .../api/health` returned `{"status":"ok"}`. Logged into
production as `verify-director@nestaprime.local`: the new sidebar and Overview dashboard
render correctly with real live figures (Pending Quotations: 3, Active Projects: 12),
every not-yet-built tile/panel correctly reads "Soon"/"Coming soon", and a side-by-side
comparison against the chosen CRM reference was produced and reviewed. Locally, both
director and sales roles were also verified before merge (Team & Access/Vendor correctly
hidden from Sales; Tools/Admin correctly narrowed to the same items the old nav gave
Sales). Amendment 36 (Phase 1 of 9) is now fully closed.

**Director decision, 22 September 2026: `verify-director@nestaprime.local` intentionally
left active in production**, rather than deactivated immediately per this account's usual
try/finally discipline -- the Director wants it available across the next several
amendments' live verification rather than reactivating it each time, with a single
consolidated deactivation once that batch is audited. Tracked here so it isn't lost; this
account must be deactivated before this is treated as closed.

### Amendment No. 37 — Existing-Client Selection Never Auto-Fills City
**Registered 22 September 2026** (from the Director's screenshot-reported UX complaints,
`docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md` Section A.1, re-confirmed
by direct read before registering). `frontend/src/ProjectSetup.jsx:64` hardcodes
`city: "Mumbai"` in `emptyForm`; the effect that fires when an existing client is selected
(`ProjectSetup.jsx:137-141`) auto-fills `package` and `paymentTerms` only -- a grep for any
property read off `selectedExistingClient` (line 120) besides deriving
`effectiveClientType` returns zero hits, confirming no client field, including city, is
ever copied into `form.city`. Root cause is structural, not a missed line: `Client`
(`backend/app/models/client.py:36`) has no structured `city` column at all, only free-text
`billing_address`. A Sales rep re-selecting a known client for a new project sees "Mumbai"
regardless of that client's real city, and must remember to correct it. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Spec approved 22 September 2026 ("approve as proposed, all decisions"). Implemented 24
September 2026 as two ordered PRs (#193 backend + migration, #194 screens), merged as `ba95381`
and `54ff6a0`.**
- **Part A (PR #193).** A nullable `Client.city` (String 100) -- the definition reused from the old
  paused branch `amendment-37-client-city-autofill`, whose open scope question (create-only vs. also
  editing) Amendment 47's client editing settled -- via hand-written migration `c37a4e8b2f19` (run
  up, down and up on the development database). `ClientCreate`, `ClientDetailsUpdate` (Amendment 47's
  edit endpoint) and `ClientOut` gain `city`: optional, trimmed, blank means none, at most 100
  characters (422 beyond), touched on edit only when sent. **Not audit-logged**, like phone and email
  (only a client rename is); same `sales`/`pm`/`director` gate as the other detail edits. **Not
  backfilled from `billing_address`** -- free-text parsing could silently give a real client the
  wrong city. A client's city never changes an existing project.
- **Part B (PR #194).** An optional City field on "Add a client" and on the client's "Edit details"
  form (pre-filled on edit). In Project Setup, choosing an existing client pre-fills the project's
  city from that client's own record **only when it has one**; a client with no city leaves whatever
  the user already had (never forced back to "Mumbai" or blank). It applies once per selected
  client, so the user's own later change is never overwritten, and it also works from a Won lead's
  "Start Project" (client already locked).
- **Two things beyond the spec's literal wording, both needed for correctness.** (1) The spec says to
  extend the effect that fills package and payment terms, but that effect only re-runs when the client
  **type** changes, so two clients of the same type would never re-trigger a city fill -- the city
  fill is its own effect keyed on the selected client. (2) The city dropdown (`SelectWithOther`)
  decides whether to show its "Others" text box only when it first appears, so a client city that is
  not on its list (e.g. Nagpur) needs a remount key. **Verified by removal:** without the key, picking
  a Nagpur client leaves the field showing "Mumbai" -- a project would be submitted under the wrong
  city with no sign of it.
- **Deliberately not done:** city is not shown as a column in the client list (spec decision 2), and
  it is not copied from a project's city when a client is created inline in Project Setup (not in the
  spec; a head-office city and a project's site city can differ).

**Verified locally.** 13 new backend tests (75 pass across them and the related client suites:
defaults to null; create with a city, trimmed; blank creates none; over-long refused on create and
edit; add / omit / clear on edit; no audit row; sales may edit and procurement may not; an existing
project's city unchanged; city not derived from the billing address); the migration run up, down and
up; and real Chrome against the local API -- 31/31 checks (Add a client and Edit details; Project Setup
filling a listed city, an unlisted city shown in the Others box, leaving the user's value when the
client has none, not overwriting the user's own choice, filling for a second client of the same type,
and switching back to the dropdown; the Won-lead "Start Project" path; Sales; no sideways overflow at
375 and 414px; no JS errors).

**Deployed to production 24 September 2026 (`54ff6a0`), backend first and then the frontend.** The
migration ran (`b50a7c1d9e42 -> c37a4e8b2f19`) and both workers started cleanly. Production's OpenAPI
now has `city` on `ClientOut`, `ClientCreate` and `ClientDetailsUpdate` (the last two capped at 100
characters), with the payments routes still present and anonymous `GET /clients` and `PATCH
/clients/{id}/details` answering 401. The served bundle changed (`index-BGiDOpm9.js` ->
`index-BPfOBPdb.js`); downloaded from production it contains the City field ("City (optional)" on both
forms, and the placeholder "Pre-fills the city of this client's new projects") and still contains every
earlier release. **A first attempt shipped nothing:** the frontend was rebuilt and copied while the server
was still at the older commit `e19880e` (no `git pull` first), so it rebuilt the old code and the bundle
name did not change -- caught by checking the served bundle name and the API, not the paste.

**Open items -- not verified or not done:**
- *Existing clients have no city*, and none is guessed, so the auto-fill will do nothing for them
  until someone fills the City in from Leads & Clients; it only starts to help as cities are entered.
- *No logged-in check on production*, and no production client's city has been looked at: the auto-fill's behaviour on real data is unverified (every existing client has no city until one is entered).
- The paused branch `amendment-37-client-city-autofill` (one WIP commit) is superseded and can be
  deleted; it has not been.

### Amendment No. 38 — Create-Cost-Sheet Form Stays Live After a Sheet Already Exists
**Registered 22 September 2026** (from the Director's screenshot-reported UX complaints,
Section A.2, re-confirmed by direct read). `frontend/src/Documents.jsx:451-477`: the
create-cost-sheet input and button are gated only on `role !== "sales"`
(`Documents.jsx:451`) -- confirmed by direct read that neither the input (453-459) nor its
wrapping section is ever hidden once an active Cost Sheet exists for the project; the
button (468-474) is only `disabled={!!active}` (line 470), not removed. A PM/Director
looking at a project that already has a Cost Sheet still sees a live "create one" form
sitting above it, confusing about whether a second one is wanted. Sales sees this too
today only because the gate is role-based, not existence-based -- although Sales cannot
submit it either way (`COST_ROLES`). Needs a Director-approved spec before implementation,
per this register's own Change Process.

**Spec approved 22 September 2026 ("approve as proposed, all decisions"). Implemented 24 September
2026 (PR #192, merged and deployed as `e19880e`; Amendments 38 and 39 shipped together).** Frontend
only (`Documents.jsx`).

**One deliberate deviation from the spec's literal wording.** Item 1 says to add `&& !active`. But the
input/button pair does two jobs: "Create Cost Sheet" when none exists, and **"Revise (new R+1)"** for a
**Verified** sheet. `&& !active` would have removed the Revise flow, contradicting the spec's own item 2
("no change to ... the Revise flow"). The pair is therefore shown when there is **no sheet (create) or
a Verified sheet (revise)** and hidden for **Draft** and **Unverified** (skip-generated) sheets, the only
states where it did nothing (a live-looking input over a permanently greyed-out button). Sales behaviour
is unchanged.

**Verified.** Real Chrome against the local API, per Cost Sheet state: no sheet -- the create form is
exactly as before, with the skip-request flow and the "start an empty Cost Sheet" link unaffected;
**Draft -- form gone entirely** (no input, no disabled button); **Unverified -- gone**; **Verified -- the
Revise flow still there**; Sales sees no form in any state; **Create still works** (the sheet appears and
the form then disappears) and **Revise still works** (a new R2 draft, R1 superseded); no sideways
overflow at 375 and 414px; no JS errors.

**Deployed to production 24 September 2026 (`e19880e`).** Confirmed by the served bundle changing
(`index-D8AQs2CR.js` -> `index-BGiDOpm9.js`) and by downloading it: it still contains "Revise (new R+1)",
"Create Cost Sheet", "start an empty Cost Sheet" and "request to skip this stage", and the Create
button's styling no longer carries the `disabled:opacity-50` class that marked the dead state.

**Open items:** no logged-in check on production; the Sales role was checked on one project only; the
spec's wording (item 1) was not followed literally, for the reason above -- the Director may prefer to
amend the spec text.

### Amendment No. 39 — Scope Checklist Has No Bulk "Not Applicable" Control
**Registered 22 September 2026** (from the Director's screenshot-reported UX complaints,
Section A.3, re-confirmed by direct read -- the Director noted this had already been
raised once before and not acted on). `frontend/src/ScopeChecklist.jsx` renders 30
checkboxes (`ScopeChecklist.jsx:97-100`), each toggled individually through a single
`handleToggle` function (`ScopeChecklist.jsx:32-46`) -- confirmed by grep that no
select-all/bulk pattern exists anywhere in the 110-line file. Unchecked items are excluded
by design (Part I, Exclusions) -- correct behaviour -- but a Sales rep who wants to
exclude most of the 30 items (the common case for a simple single-sport project) must
click each one individually with no shortcut. Needs a Director-approved spec before
implementation, per this register's own Change Process.

**Spec approved 22 September 2026 ("approve as proposed, all decisions"). Implemented 24 September
2026 (PR #192, merged and deployed as `e19880e`, with Amendment 38).** Frontend only
(`ScopeChecklist.jsx`): each of the six groups gains **Select all** and **Clear all**, scoped to that
group, using the same add/remove calls a single tick already makes (no new endpoint, no new "reviewed"
state), plus a per-group "(n of m)" count. Select all disables when the group is full and Clear all when
it is empty. **Each item saves independently, so the list only ever shows what really saved:** if some
fail, the successes stay and the message says how many did not. No confirmation dialog (spec decision 2).

**Verified.** Real Chrome against the local API on a fresh project: starts at 0 of 30 with every Clear
all disabled; Select all on Electrical checks exactly its 7 items and the API holds exactly those 7, other
groups untouched and the "N of 30 included" line updating; an individual tick still works; Select all after
a manual tick adds only the missing items (no duplicates, no error); Clear all removes that group only and
the API agrees; **a forced HTTP 500 on one item left the screen and the API both at 3 of 4** with "1 of 4
items could not be saved (forced failure). The list shows what was saved."; no sideways overflow at 375 and
414px; no JS errors.

**Deployed to production 24 September 2026 (`e19880e`).** The downloaded bundle `index-BGiDOpm9.js`
contains "Select all", "Clear all", "could not be saved" and "The list shows what was saved.", and still
contains every earlier release (Payments, Quotations, the What's-next hints, the Leads & Clients search).

**Open items:** no logged-in check on production; the checklist was not clicked through as a Sales user
(it has no role gating); a bulk action sends one request per item at once (at most nine for the largest
group).

### Amendment No. 40 — No "What's Next" Guidance for Sales Across the Document Stages
**Registered 22 September 2026** (from the Director's screenshot-reported UX complaints,
Section A.5, re-confirmed by direct read). `frontend/src/Documents.jsx`'s stage headers
(`Documents.jsx:384` Cost Sheet, `:600` Estimate, `:1068` Quotation, `:1434` Work Order)
each show only the stage's own status badge/SLA note -- confirmed by a whole-file grep for
"your turn"/"whose turn"/"what's next"/"next step"/"awaiting sales/pm/director" returning
zero matches. A Sales rep who has done their part (e.g. created the project, requested a
skip) has nothing on screen telling them whose court the ball is in or what happens next --
the exact bottleneck the Director named as the app's central problem to solve
("my hole point round to sales persons or his actual bottle neck"). Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Spec approved 22 September 2026 ("approve as proposed, all decisions"). Implemented
24 September 2026 (PR #181, deployed `c555a3c`).** Frontend only (`Documents.jsx`), no
migration: a one-line "What's next:" hint under the Cost Sheet, Estimate and Quotation stage
headers, computed client-side from statuses the panels already hold, visible to every role; a
state with no honest hint shows nothing. The Work Order stage is deliberately not covered (the
spec lists three stages).

**Verified.** Every hint was read in real Chrome (Sales user) against real local projects in
all 16 distinct (cost sheet | estimates | quotations) states, next to the status badges on the
same screen, at 1280px and 375px (no JS errors, 0px sideways overflow). That comparison found
and fixed four cases where a hint would have contradicted the screen -- the spec's own
acceptance criterion: a skip-generated (Unverified) Cost Sheet already permits an Estimate
(backend `create_estimate` and the UI both allow it) but the hint said a Verified one was
required; the Cost Sheet kept saying "an Estimate can now be created" after one existed and the
Estimate kept saying "a Quotation can now be created" after one existed; and a rejected
Estimate read "Awaiting send to client" beside a "rejected" badge.

**Deployed to production 24 September 2026 (`c555a3c`).** Confirmed by the served bundle
changing (`index-B7lZRA0W.js` -> `index-B2931D9s.js`) and by downloading it and finding the
"What's next:" label and the hint sentences.

**Open items:**
- *Copy not yet reviewed by the Director.* The spec (Open Decision 1) asks for the wording to
  be reviewed against a live preview; the wording shipped is the spec's indicative copy.
- *No logged-in check on production.* The served files were checked; a project's Documents
  screen was not opened on production.
- *States not seen rendered:* a Sent-and-awaiting Estimate, a Lost Quotation and a
  demand-received option do not occur in the local data; those code paths exist but were only
  reasoned about. Roles other than Sales were not clicked through (the hints have no role
  gating).

### Amendment No. 41 — Overview Visual Reskin (Serif/Amber Theme, Live Clock, Motion)
**Registered 22 September 2026**, from a Director-supplied HTML/CSS/JS reference file
(`Desktop\NPS-APP\HTML_Code.html`) and a direct side-by-side comparison against the live
Overview page confirming the Director's earlier "dynamic and interactive" request
(Section D of the plan doc) meant this level of visual treatment, not just the Amendment
36 shell's plain layout. Current state: `frontend/src/index.css`'s Amendment 1 theme
(dark base, gold `#c9a227`, Sora/Inter fonts) has no live clock, no motion beyond hover
lift, no animated counters/sparklines. **Scope explicitly confirmed by the Director as
visual/theme only** -- every layout position already shipped (breadcrumb top-left, top
bar top-right, tab strip, KPI tile grid, two-panel row, Recent Projects + Your Next Moves)
stays exactly where it is; nothing here repositions anything. One open question flagged
before speccing: the reference's live activity ticker is functionally the same concept as
the "Recent Activity" feed Amendment 12 explicitly *removed* from this Dashboard for being
"noise, not signal, in real usage" -- needs a real decision, not an assumption, before
building it again. Needs a Director-approved spec before implementation, per this
register's own Change Process.

### Amendment No. 42 — Client Follow-Up Date (Leads & Clients, Header Index Step 3)
**Registered 23 September 2026**, from `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`
Section B.1 and Section E step 3 (the header-by-header build index, resequenced
22 September 2026 to prioritize Leads & Clients / Follow-ups / Opportunities per the
Director's persona clarification). Re-verified 23 September 2026: `Client`
(`backend/app/models/client.py`) still has no due-date, next-action, or reminder field of
any kind -- confirmed by grep, zero matches for "follow_up"/"reminder". `Sidebar.jsx`'s
"Leads & Clients" item already routes to `ClientsAdmin.jsx` (`clients_admin`) since
Amendment 36 -- the "re-home" half of this header's step is already done; the only real
remaining work is this field. `ClientsAdmin.jsx` also confirmed to have no general
client-edit capability -- only `createClient`, `updateClientFlags` (Director-only), and
`updateClientConsent` exist (`backend/app/api/clients.py`) -- so this needs its own
narrow, purpose-built endpoint, not a slot in an edit form that doesn't exist. Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 23 September 2026 (PR #159, deployed to production same day, per
[docs/annexures/Section-48-specs.md](Section-48-specs.md), approved as proposed).** Adds
`next_follow_up_date`/`follow_up_note` to `Client` (migration `a3c7e29f5d16`), a new
`PATCH /clients/{id}/follow-up` endpoint (`sales`/`pm`/`director`, not audit-logged per
the approved spec), and an inline follow-up control on each Client Admin row (overdue
rows shown in red). 7 new backend tests, full 65-test client suite re-run clean.

**Live-verified in production:** `git pull` fast-forwarded to `708dc53`, the log
explicitly showed `Running upgrade 9e8bdbaf6219 -> a3c7e29f5d16, add client follow-up
date and note (Amendment 42)`, both gunicorn workers logged `Application startup
complete`, `curl .../health` returned `{"status":"ok"}`. Logged into production as
`verify-director@nestaprime.local`: set a real follow-up date and note on a live client,
confirmed it persisted after reload, cleared it back to null afterward (this test
modified an existing real client record's field, not a throwaway one, so left no test
data behind). Amendment 42 (Section E step 3, Leads & Clients) is now fully closed.

### Amendment No. 43 — Follow-ups (Header Index Step 4)
**Registered 23 September 2026**, from `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`
Section E step 4 (the header-by-header build index). Grounded against current code:
`Client` (`backend/app/models/client.py`) has no "owner"/assigned-rep field of any kind
(confirmed by grep, zero matches for "owner"/"assigned_to"/"rep_id") -- so a fully
personalized "my open items" view (plan doc Section B.2) is not honestly buildable yet;
only an org-wide Follow-ups view is, until a future `Opportunity.owner` field exists
(Section E step 5). `GET /clients` (`backend/app/api/clients.py:152-157`) already returns
`next_follow_up_date`/`follow_up_note` on every `ClientOut` since Amendment 42
(`clients.py:103-104`), so no new list endpoint is needed for the Follow-ups screen itself.
Three places in the current UI are already explicitly earmarked, in their own code
comments, for this exact step: Dashboard's "Follow-ups due" KPI tile
(`frontend/src/Dashboard.jsx:199`, a `ComingSoonTile`, with the file's own header comment
at `Dashboard.jsx:52-53` naming it as backend-less), the "Your next moves" panel
(`Dashboard.jsx:279-282`, a `ComingSoonPanel` whose description text literally reads
"...lands with Follow-ups (Phase 4)"), and the `DashboardSummary` Pydantic schema
(`backend/app/api/dashboard.py:29-34`), which has no `followups_due_count` field yet
alongside its four existing computed counts. The Sidebar and Dashboard tab-strip nav
entries for "Follow-ups" are both still `muted`/badged "Soon" (`Sidebar.jsx:131`,
`App.jsx:273-278` routes it to a `ComingSoon` placeholder screen). Needs a
Director-approved spec before implementation, per this register's own Change Process.

**Implemented 23 September 2026 (PR #162, deployed to production same day, per
[docs/annexures/Section-49-specs.md](Section-49-specs.md), approved as proposed).** Adds
`followups_due_count` to `DashboardSummary`/`GET /dashboard` (clients with
`next_follow_up_date <= today`), wires Dashboard's "Follow-ups due" tile and "Your next
moves" panel to real data, and adds a real `FollowUps.jsx` screen reusing `GET /clients`
-- no new list endpoint. Org-wide only, as scoped: `site_engineer`/`ca_tax` (which can
view Dashboard but not `GET /clients`) get the real KPI count but a role-appropriate
message instead of the client breakdown, rather than the whole Dashboard erroring. Drops
the "Soon" badge from the Sidebar/tab-strip "Follow-ups" nav item. One new backend test
(due-today/overdue counted, future/null excluded); no new migration (computed field, no
schema change).

**Live-verified in production:** `git pull` fast-forwarded to `408ac1b`, backend logs
showed a clean alembic context with no pending migration (as expected), both gunicorn
workers logged `Application startup complete`, both `/health` curls returned
`{"status":"ok"}` (the first direct-to-container curl transiently failed with
"Connection reset by peer" before the workers finished booting -- a pasted-command race,
resolved by re-checking logs a few seconds later, not a real fault). Logged into
production as `verify-director@nestaprime.local`: set a real follow-up date and note on
an existing throwaway "(delete me)" test client, confirmed the Dashboard tile went from 0
to 1, "Your next moves" showed the client with today's date, the full Follow-ups screen
showed it labeled "Due today" with the note, then cleared the follow-up fields back to
null and confirmed the count returned to 0 -- no test data left behind. Amendment 43
(Section E step 4, Follow-ups) is now fully closed.

### Amendment No. 44 — Opportunities (Header Index Step 5)
**Registered 23 September 2026**, from `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`
Section E step 5 (the header-by-header build index) and its locked-in design input from
23 September 2026 (Director, against the "Leads" tab of the CRM reference): a real "Lead"
vs "Client" distinction, a separate "Add Enquiry" quick-capture entry point distinct from
"Add a client", and the mandatory-follow-up-date discipline decided 22 September 2026 (a
Lead/Opportunity can never be left with no future follow-up date, enforced at creation and
whenever its stage changes or an existing date passes). The largest single piece in the
build index -- a new `Opportunity` entity, not a wiring change like steps 3-4.

Grounded against current code:
- No `Opportunity` model, table, or route exists anywhere in the codebase (confirmed by
  grep for "Opportunity"/"enquiry"/"inquiry" across `backend/app` and `frontend/src` --
  the only hit is `client.py:74`'s own comment naming it as future work).
- `Client` (`backend/app/models/client.py:32`) requires `type` (`ClientType` enum,
  `nullable=False`) at creation -- confirmed there is no path to create a `Client` row
  without picking a type, which is exactly the friction point the Design input calls out:
  a raw lead's name and phone number aren't enough to justify one. Opportunity therefore
  needs its own `lead_name`/`lead_phone`/`lead_email` fields rather than requiring a
  `Client` row to exist first; `client_id` should be nullable on `Opportunity`, set only
  once/if it's linked to or promotes an existing `Client`.
- `Project` (`backend/app/models/project.py:76-179`) requires many fields no Lead would
  ever have yet (`site_condition`, `building_status`, `unit_system`, `package`,
  `number_of_courts`, etc., all `nullable=False`) -- confirmed "converts into a Project
  once Won" cannot mean an automatic silent conversion; it means a hand-off into the
  existing New Project Setup flow. `ProjectSetup.jsx` (`frontend/src/ProjectSetup.jsx:99,
  168, 212`) already supports picking an existing client via `form.existingClientId`, so
  the hand-off point already exists -- only pre-filling it from a Won Opportunity is new.
- `created_by_id: Mapped[uuid.UUID] = mapped_column(..., ForeignKey("users.id"),
  nullable=False)` is an established pattern already used on `CostSheet`/`Estimate`/
  `Quotation` (`document.py:148,249,408`), `PriceRequest`, `PurchaseOrder`, `SiteSurvey`,
  and `WorkOrder`/`WorkOrderPaymentEntry` -- reused here as `Opportunity.created_by_id`,
  which doubles as the "owner" field Amendment 43's registration explicitly flagged as
  missing (`Client` has none), closing that gap for Opportunities going forward.
- Stage-transition endpoints elsewhere (`documents.py`'s `mark_quotation_won`/
  `mark_quotation_lost`, lines 2589-2640) do not call `write_audit_log_entry` for the
  status change itself -- confirms this codebase's audit log is reserved for
  governance-relevant facts (blacklist/consent/evidence-waiver), not routine workflow
  transitions, same convention Amendment 42 already followed for `next_follow_up_date`.
  Opportunity stage changes should follow the same non-audited convention.
- `QuotationStatus`/`EstimateStatus` (`document.py:39-85`) are the established pattern for
  a lifecycle enum on a `str, enum.Enum` -- `OpportunityStage` follows the same shape.

Needs a Director-approved spec before implementation, per this register's own Change
Process.

**Implemented, Phase A only, 23 September 2026 (PR #164, deployed to production same day,
per [docs/annexures/Section-50-specs.md](Section-50-specs.md), approved as proposed).**
Ships the backend foundation, shell-first per the approved spec's phasing: the
`Opportunity` model, `OpportunityStage` enum, `Project.opportunity_id` back-link, and the
`POST /opportunities` / `GET /opportunities` / `PATCH .../stage` / `PATCH .../follow-up` /
`PATCH .../link-client` endpoints, with the mandatory-follow-up-date discipline enforced
at the API layer (required at creation and every non-terminal stage change, auto-cleared
on Won/Lost). 23 new backend tests. Add Enquiry UI, the Opportunities screen, the Won ->
Start Project hand-off, and Dashboard/Follow-ups-screen wiring are **not yet built** --
still pending as later phases of this same Amendment, not yet registered as separate
Amendment numbers.

**Live-verified in production:** `git pull` fast-forwarded to `e3c0fc4`, the log explicitly
showed `Running upgrade a3c7e29f5d16 -> d0d627473d3c, add opportunities table and project
opportunity_id (Amendment 44)`, both gunicorn workers logged `Application startup
complete`. Logged in as `verify-director@nestaprime.local`: created a lead-only
Opportunity via the API, confirmed creation without a follow-up date is rejected (422),
confirmed a non-terminal stage change without a fresh date is rejected (400), moved it to
Won and confirmed the date cleared automatically, confirmed it appears under the
`relationship=lead` list filter. Left in place as a harmless (Won, terminal) throwaway
record -- no delete/rename endpoint exists yet for Opportunities.

**Implemented, Phase B, 23 September 2026 (PR #166, deployed to production same day).**
Ships the UI half: "Add Enquiry" quick-capture on `ClientsAdmin.jsx` (mandatory follow-up
date, pre-filled two days out) and a new `Opportunities.jsx` screen (All/Leads/Clients
relationship tabs, stage pill, inline stage-change and follow-up-date editing,
link-to-existing-client). Sidebar/tab-strip drop the "Soon" badge. The Won -> Start
Project hand-off and Dashboard/Follow-ups-screen wiring are still pending as later phases.

**Live-verified in production:** `git pull` fast-forwarded to `0133eed`, the frontend
Docker build completed cleanly, `/api/health` returned `{"status":"ok"}`. Logged in as
`verify-director@nestaprime.local`: used "Add Enquiry" to create a lead-only Opportunity,
confirmed it appeared on the Opportunities screen under "Leads", linked it to an existing
throwaway "(delete me)" Client (confirmed it moved to the "Clients" filter), then set its
stage to Lost -- left in that terminal, harmless state.

**Implemented, Phase C, 24 September 2026 (PR #170, deployed to production same day).**
Ships the Won -> Start Project hand-off (spec item 6): a "Start Project" button on a Won,
Client-linked Opportunity opens New Project Setup with the client locked; `POST /projects`
accepts `opportunity_id` and validates it before creating anything (must exist, be Won, be
linked to the same Client, not already converted); the Project's `opportunity_id` and the
Opportunity's `project_id` are set together. 7 new backend tests. No migration.

**Live-verified in production:** `git pull` fast-forwarded to `2806240`, no migration line
(correct), both gunicorn workers `Application startup complete`, `/api/health` OK. As
`verify-director@nestaprime.local`, started a Project from a Won throwaway Opportunity
through the real UI (P-2609-0020, on a "(delete me)" client), confirmed the two-way link
via the API, and confirmed a second project from the same Opportunity is rejected (400).

**Implemented, Phase D, 24 September 2026 (PR #171, deployed to production same day).**
Ships spec items 7-9: real "Open opportunities" tile and "Sales pipeline" panel (counts only,
no fabricated value); `followups_due_count` summing due Clients and due open Opportunities;
due leads in "Your next moves"; and one combined Clients + Opportunities Follow-ups queue with
a "My follow-ups" toggle. The toggle narrows leads to the ones the signed-in user created
(`Opportunity.created_by_id`) and keeps Clients visible with a note, since `Client` has no
owner field -- closing the "my open items" gap Amendment 43's registration flagged as blocked
on this step. 5 new backend tests. No migration.

**Live-verified in production:** `git pull` fast-forwarded `2806240..0caf69d`, no migration
line (correct), both workers `Application startup complete`, `/api/health` OK; deployment
confirmed by production's own `/api/dashboard` returning the new fields and the frontend
bundle changing. With a throwaway due-today lead, the Dashboard tile/pipeline/"Your next
moves" and the Follow-ups screen (including the "My follow-ups" toggle and an in-place save)
all behaved correctly; the lead was closed as Lost and every count returned to 0.

**Amendment 44 is now fully closed** (Phases A-D all deployed and live-verified).

### Amendment No. 45 — Leads & Clients Polish: Hide Admin-Only Flags, Add Notes Field
**Registered 23 September 2026**, from a direct Director review of the Sales-facing
surface audit above. Two related fixes to the Leads & Clients / Opportunities screens,
both already Director-approved in the same message that raised them:

1. **Hide Overdue/Blacklisted from non-Director roles.** `ClientsAdmin.jsx` (lines
   344-369, pre-fix) showed these two checkboxes to every role, only disabled (with a
   "Director only" tooltip) for non-directors -- Sales saw two greyed-out admin controls
   it can never use on every single client row, exactly the kind of admin-area clutter
   the audit flagged as not needed for the Sales persona. Fixed directly (no schema/API
   change, pure visibility): wrapped both in `{canEditFlags && (...)}` so they render only
   for a Director; the consent-toggle divider (`border-l`) is now conditional too, so
   Sales's row doesn't show an orphaned left border where the hidden controls used to be.
   **Already implemented and verified locally** (screenshotted as both `sales` and
   `director` test accounts) as of this registration -- a UI-only correction to already-
   shipped Amendment 42/43 functionality, not a new capability, same category as this
   register's earlier "sizing fix"/"structural gap" direct fixes.
2. **Add a general Notes/Remarks field to "Add a client" and "Add Enquiry".** Grounded
   against current code: `Client` (`backend/app/models/client.py`) has no general
   free-text field at all -- its closest relative, `next_follow_up_date`/`follow_up_note`
   (Amendment 42), is specifically about the *next follow-up reminder*, not a catch-all
   note, and isn't even part of the client-creation form (`ClientCreate` in
   `backend/app/api/clients.py`), only editable afterward via the separate inline
   follow-up editor. `Opportunity` (`backend/app/models/opportunity.py`) has the same gap
   at creation -- `OpportunityCreate` accepts `lead_name`/`lead_phone`/`lead_email`/
   `next_follow_up_date` only, no general note. The established precedent for exactly this
   need already exists on `Project`: `custom_notes: Mapped[str | None] = mapped_column(
   Text, nullable=True)` (`project.py:172`), Amendment 5's "+ Add Note" -- "one note per
   project (not per screen)," a free-text catch-all distinct from any structured field.
   Needs a Director-approved spec before implementation, per this register's own Change
   Process.

**Implemented, 23 September 2026 (PR #168, deployed to production same day, per
[docs/annexures/Section-51-specs.md](Section-51-specs.md), approved as proposed).** Item 1
(hiding Overdue/Blacklisted) shipped as a direct fix, verified locally before this PR.
Item 2 ships `Client.notes`/`Opportunity.notes` (`Text`, nullable), new `PATCH
/clients/{id}/notes` and `PATCH /opportunities/{id}/notes` endpoints
(`sales`/`pm`/`director`, not audit-logged), a textarea on both "Add a client" and
"Add Enquiry", and inline edit-and-save on every existing client/opportunity row. 20 new
backend tests.

**Live-verified in production:** `git pull` fast-forwarded to `f8ed62d`, backend logs
showed `Running upgrade d0d627473d3c -> 324c6521d698, add notes field to clients and
opportunities (Amendment 45)`, the backend container came up with no restart, frontend
rebuild completed, `/api/health` returned `{"status":"ok"}`. Logged in as
`verify-director@nestaprime.local`: created a client via "Add a client" with notes text
and confirmed it persisted, created an Opportunity via "Add Enquiry" with notes text and
confirmed the same, then cleared the client's notes and moved the Opportunity to Lost
(terminal, harmless) -- no live test data left active. Amendment 45 is now fully closed.

### Amendment No. 46 — Completed-Header Audit Fixes (Overview, Leads & Clients, Opportunities, Follow-ups)
**Registered and implemented 24 September 2026**, at the Director's instruction to check the
completed headers before starting the next one. Small corrections to already-delivered work,
made directly (same category as this register's earlier sizing/structural fixes -- no new
capability, no schema or API change). Method: an API role matrix (`sales`, `pm`, `director`,
`procurement`, and throwaway local `site_engineer`/`ca_tax` accounts) against `/dashboard`,
`/clients`, `/opportunities`; real-UI walkthroughs as `site_engineer`, `ca_tax`, `sales` and
`director`; a scripted click-through of all four screens with error capture (zero JS errors);
and a code scan for placeholder/developer wording.

**What held up:** every role gets `/dashboard` with the Phase D fields (200); `pm`/`procurement`
can read clients and opportunities; `site_engineer`/`ca_tax` are correctly refused (403) on the
two lists, and the Dashboard degrades cleanly for them (real counts, no "View all" link,
"Follow-up details aren't available for your role").

**Defects found and fixed:**
1. *Data-honesty bug.* For a role refused by the API, Follow-ups, Opportunities and Leads &
   Clients showed the permission error **and** an empty-state line ("No client or lead has a
   follow-up date set right now") -- false, since records existed; the role simply could not
   see them. The empty-state line is now suppressed when the load itself failed.
2. *Dead navigation.* `site_engineer`/`ca_tax` were offered Leads & Clients, Opportunities and
   Follow-ups (sidebar and Overview tab strip), which could only ever error. Hidden for those
   roles (`Sidebar.jsx`, `Dashboard.jsx`), same idea as Team & Access being hidden from Sales.
3. *Naming/copy.* The "Leads & Clients" header opened a page titled "Clients" with a paragraph
   of blueprint text ("Part O: overdue_flag ..."); consent tooltips cited "M.7.2 rule 5" and
   "Amendment 8"; the Overview panel said "lands with Payments (Phase 7)". All replaced with
   plain user-facing wording; the Director-only flags sentence now shows only to a Director.

**Verified after the fixes (local, real UI):** `ca_tax` sidebar/tab strip = Overview,
Quotations, Projects, Payments, Team & Access; Sales sees "Leads & Clients", the plain blurb,
no Overdue/Blacklisted controls, plain tooltips and the full nav; Director additionally sees
the flags sentence and the Overdue/Blacklisted checkboxes.

**Deployed to production 24 September 2026 (PR #174, `1ab5a89`).** Frontend-only; deployment
confirmed by the served bundle changing. Verified live as a Director (heading, blurb incl. the
flags sentence, checkboxes, tooltip, Overview wording, nav intact); the `site_engineer`/`ca_tax`
and Sales-role behaviours were verified locally on the same build (no such production accounts).

**Open items -- deliberately NOT fixed here, need a Director decision or a real device:**
- *No way to correct a lead's name/phone/email* after "Add Enquiry" (only stage, follow-up,
  notes and client link are editable). A typo in a telecaller's lead is permanent. Small
  endpoint + UI; recommended.
- *Leads & Clients is still one flat client list in the old admin styling.* The Lead/Client
  tabs from the Director's 23 September design input were built on the Opportunities screen
  instead. Decision needed: add the tabs to Leads & Clients too, or accept the current split.
- *Phone-width layout is unverified.* The browser emulator reported a 581px viewport for a
  375px request and rendered the desktop sidebar, so its result is not trustworthy; needs a
  check on a real phone or resized real browser.
- *Sales role not exercised in production* for these headers (no active production Sales
  account); verified locally and in the deployed code path only.

### Amendment No. 47 — Complete the First Three Headers (Lead/Client Details, Leads & Clients Tabs, Phone Layout)
**Registered 24 September 2026**, from the Director's decision on the open items Amendment 46's
audit recorded: complete Overview, Leads & Clients and Opportunities -- specifically (1) editing
lead details, (2) Lead/Client tabs on Leads & Clients, and (3) the phone layout -- *before*
starting the next header. Grounded against current code:
- **No way to correct a name/phone/email.** `opportunities.py` has only `stage`, `follow-up`,
  `link-client` and `notes` PATCH endpoints (lines 135/168/189/211); `clients.py`'s
  `PATCH /{client_id}` (line 181) is the Director-only flags endpoint, alongside `consent`,
  `follow-up`, `notes` (215/248/273). A typo in a lead's *or a client's* name, phone or email is
  permanent today -- the same gap on both entities, though only the lead half was raised.
- **Leads & Clients is one flat client list.** `ClientsAdmin.jsx` (`max-w-3xl`, line 221) renders
  "Add a client" (242) and "Add Enquiry" (318) *above* the list (387), so a rep scrolls past two
  forms to reach anyone; no search; leads (lead-only Opportunities) do not appear on it at all --
  the Lead/Client distinction from the 23 September design input exists only on Opportunities.
- **Phone layout is broken on all four completed headers.** Measured in real Chrome mobile
  emulation (touch, 375px, correct viewport meta -- not the earlier unreliable pane emulator):
  the width each screen needs is Overview **581px**, Leads & Clients **753px**, Opportunities
  **641px**, Follow-ups **522px**, against a 375px phone. Screenshots show real damage
  (truncated headings "Opportunit...", cut-off buttons, controls overflowing their cards).
  **Root cause of the largest part:** `App.jsx:150` wraps the page in
  `<div className="flex min-h-screen">` (a *row*); `Sidebar.jsx`'s mobile top bar (`sm:hidden`,
  line ~258) is a sibling of `<main>`, so on a phone it becomes a ~180px left *column* beside the
  content instead of a bar above it -- squeezing the real content to roughly 190px. The rest is
  fixed-width controls (`w-32`, `min-w-[8rem]`, `shrink-0` clusters) and non-wrapping header rows.
Needs a Director-approved spec before implementation, per this register's own Change Process
(spec: `docs/annexures/Section-52-specs.md`).

**Spec approved 24 September 2026 ("approve as proposed, all decisions").** Delivered as three
ordered PRs, each merged, deployed and checked against what production actually serves
before the next began.

**Part C -- phone layout (PR #176, deployed `10a58f6`).** Root cause fixed at `App.jsx:150`
(`flex flex-col sm:flex-row`), plus wrapping/stacking of header rows and control clusters and
responsive widths on the four screens. **Verified** in real Chrome mobile emulation (touch,
correct viewport) as a Sales user: the width each screen needs went from 581 / 753 / 641 /
522px to exactly the viewport width at **375, 414, 768 and 1280px**, with no overflowing
elements, a working hamburger menu and zero JS errors.

**Part A -- edit details (PR #177, deployed `8b71a35`).** `PATCH /opportunities/{id}/details`
and `PATCH /clients/{id}/details`; blank names refused after trimming; omitted contact fields
untouched, null/blank clears them; leads editable at any stage; clients `sales`/`pm`/`director`;
client *type* not editable; only a client **name** change is audit-logged. Shared inline
`EditDetailsForm` on Opportunities and Leads & Clients (hidden from Procurement); client cards
now show their contact line. 17 new tests (68 related pass); real-Chrome check 12/12 at 375px.
No migration.

**Part B -- Leads & Clients restructure (PR #178, deployed `e535432`).** All / Leads / Clients
tabs with counts (leads = lead-only, non-Lost Opportunities), Lead/Client badge per row, lead
rows with Edit details and "Open in Opportunities ->", name/phone/email search, collapsible Add
Enquiry / Add a client forms, restyled header, and a failed load no longer shows a false empty
state. Frontend only. Real-Chrome check 24/24, including tab counts equal to the API's own
numbers, no overflow on any tab at 375px, and a separate desktop pass at 1280px.

**Verified live (24 September 2026):** after each deploy, by what the server returns rather
than the pasted output alone -- the served bundle changed each time (`index-DeWY-Pec.js` ->
`index-NczabCfy.js` -> `index-ida_2CSV.js` -> `index-B7lZRA0W.js`), the downloaded bundles
contain the new layout / Edit details / tabs-and-search text, and production's OpenAPI lists
both new `/details` routes (an unauthenticated PATCH returns 401, a nonexistent route 404).

**Open items -- not verified or not done:**
- *Real phone not yet tested.* All phone results are real-Chrome mobile emulation. The
  Director could not open the site on their phone ("This site can't be reached"); the site is
  plain HTTP on a bare IP, and phone browsers and mobile networks increasingly refuse or
  rewrite that to HTTPS. The site itself was confirmed up over HTTP from the development machine. **Suggested, not
  yet registered:** HTTPS on a proper domain name (also stops passwords crossing the network
  unencrypted).
- *No authenticated click-through on production.* Parts A and B were exercised through the real
  UI locally; production was checked for the served code and the routes, not by logging in and
  editing a record. No active production Sales account exists to test that role.
- *Local test data quirk:* the local dev database has a client with a blank name; the new form
  correctly refuses to save that client until it is given a name. Whether production has any
  blank-named client was not checked.

**Next:** the next header, What's-next guidance (Amendment 40, spec Section 46, already
approved), resumes from the shelved work.

### Amendment No. 48 — CRM Header Gap Audit (All Eight Sidebar Headers vs. the Plan)
**Registered 24 September 2026**, from the Director's request, after Amendment 47 closed the
first three headers, to audit every CRM sidebar header against the plan
(`docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`, Sections D0 and E) and the
current code before choosing what to build next. **This entry is a record of findings, not a
change:** it implements nothing, and each gap below needs its own Director-approved spec under
this register's Change Process before being built.

Findings (read from the code and register, not from memory; no live click-through):

| Header | Status | Gaps |
|---|---|---|
| Overview | Done (36, 41, 46) | "Payments overdue" tile and "Orders & collections" panel are honest placeholders until Payments exists |
| Leads & Clients | Done (42, 45, 46, 47) | `Client` has no owner field, so no per-rep "my clients" |
| Opportunities | Done (44) | No link from a Quotation back to the Opportunity that produced it (plan step 8); "Open in Opportunities" opens the screen, not the record |
| Follow-ups | Done (43, 44D) | None known |
| Quotations | **Not done** | `Sidebar.jsx` `onQuotationsClick`: for every role except Director the item calls `handleNewProject()` -- it starts a new project rather than showing quotations; only the Director reaches a quotation list. Estimates still has no nav entry (plan mismatch #2) |
| Projects | **Partly done** | Amendment 35 shipped. Approved but **not shipped:** 37 (city auto-fill -- `ProjectSetup.jsx:64` still hard-codes `city: "Mumbai"`), 38 (cost-sheet form stays live), 39 (scope-checklist bulk "not applicable"), 40 (what's-next guidance; half-built, shelved in `git stash@{0}`) |
| Payments | **Not built** | Routes to `ComingSoon`; `WorkOrderPaymentEntry` exists but has no due dates, overdue tracking or screen; **nothing registered** for it |
| Team & Access | **Never audited** | Nav item opens the Master Settings screen (User management and Role permissions tabs) -- a naming mismatch; contents confirmed by code read only |
| More (Vendor, Tools, Reports, Admin, Education) | Placement decisions never signed off | Plan E.1 still lists them "needs a decision"; Help still sits inside Admin (mismatch #3); Reports gives Sales no note that only the Pipeline type is available (mismatch #4) |

Cross-cutting gaps: **global quick search** (plan B.3) does not exist -- the only search is the
one added to Leads & Clients in Amendment 47. **Quotation descriptiveness** (plan Section C) was
never registered as an amendment; the Terms & Conditions setting already exists
(`quotation_terms_and_conditions`), but whether the richer cover letter, descriptive scope of
work and bank details exist was not confirmed. **Unverified in production:** the layout on a
real phone (the operator's phone could not open the plain-HTTP, bare-IP site; HTTPS on a proper
domain is suggested and still unregistered) and the Sales role (no active production account).

**Recommended order (Director to confirm each):** (1) Amendment 40, What's-next guidance --
approved, half-built; **started 24 September 2026 on the Director's instruction.** (2) Quotations
header (plan step 8). (3) Payments (plan step 9; needs a spec). Then the approved leftovers 37-39,
Team & Access naming (plan step 10) and the More-group placement decisions. Each becomes its own
Amendment with its own spec.

### Amendment No. 49 — Quotations Header (Header Index Step 8; Gap 1 of Amendment 48's Audit)
**Registered 24 September 2026**, on the Director's instruction to spec the Quotations header
after Amendment 40, from Amendment 48's audit finding that it is the most misleading item left
in the sidebar. Grounded against current code:
- **The "Quotations" nav item is not a Quotations screen for most roles.** `Sidebar.jsx`
  `onQuotationsClick` opens the quotation list only for a Director; for every other role it
  calls `handleNewProject()`. The Overview's "Quotations" tab does the same
  (`Dashboard.jsx` `quotationsTabClick`, lines 205-208). `POST /projects` is limited to
  `sales`/`pm`/`director` (`projects.py`), so `procurement`, `site_engineer` and `ca_tax` -- who
  are all shown the item -- land on a project form they cannot submit.
- **The only quotation list is Director-only.** `GET /quotations`
  (`quotations_admin.py`, `ROLES = ("director",)`) returns cost, margin and below-floor per
  row. The Overview's "Pending quotations" tile is therefore not clickable for anyone else
  (`Dashboard.jsx:182`, `target: null`), although the per-project quotation view already
  withholds exactly those figures from Sales (`documents.py:1900-1905`) -- so a Sales-safe list
  has a ready-made rule.
- **Estimates has no header.** `GET /estimates` is open to six roles and carries no
  cost/margin (`estimates_admin.py`), but its screen is reachable only from a Dashboard tile or
  a project's Documents screen (plan mismatch #2).
- **No quotation shows which lead it came from.** `Project.opportunity_id` links a project to
  the Won Opportunity it started from (Amendment 44 Phase C), so the link the plan calls for
  (step 8) needs no new data, only to be surfaced.
Needs a Director-approved spec before implementation, per this register's own Change Process
(spec: `docs/annexures/Section-53-specs.md`, approved 24 September 2026).

**Spec approved 24 September 2026 ("approve as proposed, all decisions"). Implemented 24
September 2026 as two ordered PRs (#184 backend, #185 frontend); deployed together (`12b0e68`).**
- **Part A (PR #184, `quotations_admin.py`).** `GET /quotations` admits `sales`/`pm`/`director`.
  Sales rows return `cost_total`, `margin_percent` and `below_floor` as null (the per-project
  K.3 rule), keeping the client-facing totals; PM/Director rows unchanged. Each row carries
  `opportunity_id` and `lead_name`, surfacing the existing `Project.opportunity_id` link. The CSV
  export stays Director-only; `procurement`/`site_engineer`/`ca_tax` are still refused. 7 new
  tests and one rewritten -- the file went from 9 to 15 tests, and the old "Sales cannot list"
  test now asserts the new contract. (PR #184's description and commit message say "9 new
  tests"; that count was wrong.)
- **Part B (PR #185, frontend).** The "Quotations" nav item and the Overview tab open the list
  for Sales/PM/Director instead of starting a project, and are hidden for the three roles that
  cannot use it. The screen has Quotations and Estimates tabs (the existing Estimates list
  embedded), no Margin % column for Sales, Export CSV for the Director only, a "From lead:"
  line with an "Open in Opportunities" link, a "+ New project" button, stacked cards on phones,
  and no false "No quotations match" when a load fails. The Overview "Pending quotations" tile
  now links for Sales and PM.

**Verified.** Locally: 44 related backend tests pass; real Chrome per role -- 45 of 46
automated checks (the one miss was a test looking for placeholder text; the Estimates tab was
inspected directly and works), covering Sales/PM/Director columns and buttons, the three
refused roles' nav, list counts equal to the API's own (20 = 20; Pending 15 = 15 = 15 across the
list, the Overview tile and the API), a quotation seeded from a Won lead showing its lead line,
no sideways overflow at 375, 414 and 768px, and no JS errors. **On production**, from what the
server returns: the served bundle changed (`index-B2931D9s.js` -> `index-BY1Qsrjh.js`) and
contains the new screen text; OpenAPI lists `lead_name`/`opportunity_id` and the three nullable
K.3 fields on the quotation list; anonymous `GET /quotations` and `/quotations/export` return
401; the backend restarted cleanly.

**Deployed together, not one at a time.** The spec proposed deploying and checking Part A before
Part B. Both were merged before the first deploy, so one deploy shipped both (backend rebuild +
frontend rebuild, no migration); Part A alone was never run in production.

**Open items -- not verified or not done:**
- *No logged-in check on production.* The served code and API schema were checked; nobody
  logged in and opened the Quotations screen there, and no production Sales or PM account exists
  to test those roles.
- *Copy and layout not yet reviewed by the Director.*
- *The Overview's "Pending estimates" tile still opens the standalone Estimates screen*
  (`estimates_admin`), not the new Estimates tab; both exist. Admin > "All Quotations"
  (Director) is unchanged, per the spec.
- *Test data:* a throwaway "(delete me)" client and project were created in the local
  development database for the checks; nothing was created in production.
- *Still open from Amendment 48's audit:* Payments (unbuilt, unregistered), approved
  Amendments 37-39, Team & Access naming, the More-group placement decisions, global quick
  search, Section C quotation descriptiveness, and HTTPS on a proper domain.

### Amendment No. 50 — Payments Header (Header Index Step 9; Gap 3 of Amendment 48's Audit)
**Registered 24 September 2026**, on the Director's instruction, from Amendment 48's finding
that Payments is the largest unbuilt header and has nothing registered for it. Grounded against
current code:
- **The header is a placeholder.** The sidebar item is muted with a "Soon" badge and routes to
  `ComingSoon` (`Sidebar.jsx`, `App.jsx` `screen === "payments"`); the Overview's "Payments
  overdue" tile and "Orders & collections" panel are `ComingSoonTile` / `ComingSoonPanel`
  (`Dashboard.jsx`), shown to every role. Plan step 9 calls for exactly this header: "extend
  `WorkOrderPaymentEntry` with due-dates/reminders; surface 'payments overdue'."
- **Only money already received is recorded.** `WorkOrderPaymentEntry`
  (`models/work_order.py`) holds `milestone_name`, `amount_received`, `received_date`,
  `gst_tds_amount`, `notes`. There is no expected amount and no due date anywhere, so
  "overdue" cannot be computed from any existing data.
- **Add-only, PM/Director-only, one project at a time.** `work_orders.py` offers
  `add_payment_entry` and `list_payment_entries` only (`ROLES = ("pm", "director")`): no edit
  and no delete -- a mistyped amount is permanent, the same gap Amendment 47 closed for leads --
  and no cross-project view. The only screen is `WorkOrderPanel` on a project's Documents
  screen (`Documents.jsx:1285`), shown once a Quotation is Won and a Work Order exists.
- **Order value has no field of its own.** A Work Order is one-per-Won-Quotation
  (`create_work_order` requires `QuotationStatus.WON`); its value is that Quotation's frozen
  `quotation_total`. `Client.payment_terms` is free text ("40/40/20"), defaulted per client type
  at creation and echoed on the client; a whole-backend grep finds no use of it in any document
  or calculation -- it is never turned into a schedule.
- **There is no "won date".** `Quotation` has no `won_at` (`dashboard.py:148` documents the
  gap and uses `released_at` as a proxy), so the reference's "won value vs cash received, by
  month" chart cannot be drawn honestly from won dates; `WorkOrder.awarded_at` is the honest
  anchor.
Needs a Director-approved spec before implementation, per this register's own Change Process
(spec: `docs/annexures/Section-54-specs.md`, approved 24 September 2026).

**Spec approved 24 September 2026 ("approve as proposed, all decisions"). Implemented 24
September 2026 as three ordered PRs (#188 backend, #189 screen, #190 Overview).** Reconciliation
only -- nothing computes GST, TDS or invoices, and nothing is inferred from the client's
free-text payment terms.
- **Part A (PR #188, backend + migration `b50a7c1d9e42`).** New `work_order_payment_milestones`
  table (name, amount due, due date, notes) and a nullable `milestone_id` on receipts. Milestone
  status (pending / part paid / paid), received / TDS / settled / outstanding amounts and the
  overdue flag are **derived** in `app/services/payments.py`, never stored; overdue is strictly
  past the due date and unpaid. Endpoints for milestones (create, list, edit, delete), receipt
  edit (receipts are never deleted), a per-Work-Order summary and `GET /payments`; a `payments`
  block on `GET /dashboard`. Milestones may not total more than the order value (the Won
  Quotation's frozen `quotation_total`); receipts may exceed it and are flagged `over_received`;
  a milestone with receipts against it cannot be deleted; a receipt may only link to its own Work
  Order's milestone. Every milestone create/edit/delete and every receipt create/edit is
  audit-logged (**receipt creation was not audited before -- a behaviour change**). Writes stay
  `pm`/`director`; `ca_tax` reads; `sales`/`procurement`/`site_engineer` are refused.
- **Part B (PR #189, frontend).** Payments is a real screen: summary cards equal to the sum of the
  rows shown, All / Overdue tabs, search, and one row per Work Order expanding to its milestones
  and receipts, with add / edit / delete for PM and Director and a read-only view for CA/Tax. The
  Work Order panel on Documents uses the same shared component and links to Payments. The
  client's payment terms appear as a reminder only. The nav item and Overview tab are shown only to
  `pm`/`director`/`ca_tax`; the unused `ComingSoon` component was removed.
- **Part C (PR #190, frontend).** The Overview's "Payments overdue" tile (amount + number of Work
  Orders, "--" / "No due dates set" -- never 0 -- until a due date exists) and "Orders &
  collections" panel (totals + six-month awarded-value vs cash-received bars, with honest empty
  states) replace the last two "Coming soon" placeholders; roles without access see neither.

**Verified locally.** 28 new backend tests (81 pass across payments, work orders, dashboard and
audit log); the migration run up, down and up on the development database; real Chrome per role
against the local API -- Part B 51/51 checks (the summary cards equal the API rows' sums; a milestone
total above the order value refused; recording the balance marks a milestone paid and clears its
overdue flag; a corrected receipt writes an audit entry with old and new values; receipts have no
Delete; CA/Tax has no write controls; Sales/Procurement/Site Engineer have no Payments item) and
Part C 51/51 (the tile, the panel totals and the month bars equal the API's figures; the tile's
count equals the Overdue tab's and its amount the Overdue card; the empty states; role gating), plus
no sideways overflow at 375, 414 and 768px and no JS errors in any session.

**Deployed to production in two steps, 24 September 2026.** (1) **Backend, `f10548e`:** the
migration ran (`324c6521d698 -> b50a7c1d9e42`), both workers started cleanly, and production's
OpenAPI lists all five new payment routes and the `payments` block on the dashboard, with anonymous
calls answering 401. The first frontend deploy **did not reach the web folder** -- the copy step was
skipped -- so production kept serving the previous bundle (`index-BY1Qsrjh.js`), confirmed by
downloading it. (2) **Frontend, `6956161` (Parts B and C together):** redeployed with the copy
step; the served bundle changed to `index-D8AQs2CR.js`. Downloaded from production, it contains the
Payments screen ("What each Work Order is worth", "Expected payments", "Payments received",
"Milestones & payments", "Open in Payments") and the Overview's payments tile and panel ("Payments
overdue", "No due dates set", "counted by award date", and both empty-state messages), contains **no**
"Coming soon" text, and still contains the Quotations screen, the What's-next hints, the Leads &
Clients search and the phone layout.

**Open items -- not verified or not done:**
- *The CA has not confirmed decision 3.* The app counts TDS withheld as settled (outstanding =
  order value - received - TDS). It is an accounting judgment the spec asked to have confirmed;
  if the CA disagrees it is a one-line change in `app/services/payments.py` and its tests.
- *No logged-in click-through on production*, and no production data was inspected: what production
  shows on first load (existing Work Orders with "No expected payments set") is unverified.
- *"Overdue" uses the server's date (UTC).* For a user in India a milestone due today becomes
  overdue at 05:30 IST rather than at midnight.
- *Receipts created before this Amendment have no "created" audit entry* (creation was not
  audited); only later creates and all edits are.
- *The Overview counts Work Orders, not Won quotations:* a Won quotation with no Work Order yet is
  not in "Orders & collections" (spec decision 8; the panel says so).
- *Director review of the screens is pending*, and nothing has been tested on a real phone (the
  site is still plain HTTP on a bare IP).
- *Test data:* throwaway "(delete me)" clients, projects, Work Orders and milestones exist in the
  local development database only; nothing was created in production.
- *Still open from Amendment 48's audit:* the three approved Projects fixes (Amendments 37-39),
  Team & Access naming, the More-group placement decisions, global quick search, Section C
  quotation content, and HTTPS on a proper domain.

### Amendment No. 51 — Team & Access and Role-Accurate Navigation (Gap 4 of Amendment 48's Audit)
**Registered 25 September 2026**, from the audit of the Team & Access header (24 September) that
Amendment 48 left open, extended the next morning to the whole "More" menu. Grounded against current
code and real-Chrome sessions as each of the six roles:
- **"Team & Access" is not a team-and-access screen.** The sidebar item (`Sidebar.jsx`,
  `showTeamAccess = role !== "sales"`) opens `MasterSettings`, titled "Master Settings", on its
  *Settings* tab; the two team tabs (User management, Role & Permissions) are Director-only and
  secondary. `Admin > Master Settings` opens the identical screen under a different name.
- **The item is shown to roles the API refuses.** `GET /settings` is `pm`/`director` only
  (`settings.py`), yet `procurement`, `site_engineer` and `ca_tax` are shown the item. For them the
  screen fires **five refused (403) calls**, prints permission-error text, and says **"Current
  settings (0)"** when 29 exist -- a false empty state, the class Amendment 46 fixed for other items.
- **The same fault runs through the "More" menu.** Opening every item as each role and counting
  refused calls: Director and PM none; Sales none (its items are already hidden). `procurement`:
  Price Calculator 1, Reports 1, Sports & Scope 2, Master Settings 5. `site_engineer`: Price
  Calculator 1, Rate Sheet 1 (`/vendors`), Price Requests 2, Reports 1, Sports & Scope 2, Master
  Settings 5. `ca_tax`: Price Calculator 1, Rate Sheet 3, Price Requests 3, Reports 1, Sports & Scope
  12, Master Settings 5. Each `Sidebar.jsx` gate is `role !== "sales"` (or absent), not the roles the
  API admits.
- **PM is shown forms the API refuses.** The Master Settings Settings tab has no role check inside
  it, so PM sees Add a new setting, Bulk update, logo upload, company details, templates and field
  settings; probing the local API as PM, **all 18 write endpoints behind that screen and Admin return
  403**, including `POST /settings`, `POST /settings/bulk-update` and `POST /users`. The screen's own
  text says "PM is read-only".
- **The Role & Permissions tab is a stale hand-kept mirror.** `rolePermissionsData.js` was written
  13 September against "192 call sites across 41 files"; the code now has 243 across 49 and the file has
  never been updated. Today it says CA/Tax has Dashboard-only access (false since Payments), lists Work
  Orders & Payments as `pm`/`director` "add/list payment entries" only (missing milestones, receipt edits,
  the org list and CA/Tax read access), lists "update client flags/consent" for Sales (flags are
  Director-only), and has nothing on Opportunities, Follow-ups, the Quotations list or the Overview
  payments block -- on the one screen a Director consults to learn who can do what.
- **What is sound:** user management (`users.py`) cannot deactivate your own account, protects the last
  active Director, audit-logs every write and forces a password change on first login.
Needs a Director-approved spec before implementation, per this register's own Change Process
(spec: `docs/annexures/Section-55-specs.md`, approved 25 September 2026).

**Implemented (25 September 2026), in the spec's two ordered parts plus one follow-up.**
*Part A (backend, PR #197):* `require_roles()` now records the roles it enforces
(`dependency.allowed_roles`, behaviour unchanged) and a new Director-only `GET /role-permissions`
(`app/api/role_permissions.py`) walks the live route table and returns every role-gated route --
method, path and a humanised label -- grouped by area (first tag) and by identical role set, plus the
routes that need only a sign-in or nothing at all (`/auth/me`, `/auth/change-password`,
`/company/logo`, `/company/logo/meta`, login, health, the WhatsApp webhook). 244 gated routes in 65
areas today. *Part B (frontend, PR #198):* "Team & Access" is now a real Director-only screen with
**People** (the existing user management, moved unchanged) and **Roles & permissions** (renders the
endpoint; `rolePermissionsData.js` deleted; the three safety-critical rules stay as prose). One table,
`navAccess.js`, now decides who is shown each screen and is used by both the sidebar/More menu and the
App-level gates, so they cannot disagree; a More group with nothing left to show is hidden. Master
Settings has one entry point (Admin > Master Settings) for `pm` and `director`, and for PM it is
read-only: no add/bulk/edit/logo/import/company-details/template/field-setting controls, and no request
for the Director-only quotation-preview list. Rate Sheet no longer requests `/vendors` for roles the
API refuses (`site_engineer`). *Follow-up (PR #199, text only):* the in-app Help handbook still sent
Directors to "Master Settings > User Management / Role & Permissions"; reworded to Team & Access.
**That was missed in Part B** -- the spec did not list the handbook -- and found only when a leftover
string turned up while verifying the deployed bundle.

**Verified locally.** 8 new backend tests (`tests/test_role_permissions.py`): Director-only (401 anonymous,
403 for the five other roles); the response's routes equal OpenAPI's independent route list exactly, each
once, none both gated and ungated; 13 hard-coded gate spot-checks (e.g. `GET /payments` is
`pm`/`director`/`ca_tax`, `POST /settings` and `POST /users` are `director`, `GET /quotations` is
`sales`/`pm`/`director`); ungated classification; labels; and a gated route added inside a test appears
with no other change and is cleaned up. CI ran the full backend suite green on #196, #197, #198 and #199
(each with a `push` and a `pull_request` run). A first local full-suite attempt overlapped
a second one on the shared test database and errored at setup (the affected file passed when re-run
alone); the second, run alone on the Part A code, finished later with **1346 passed, 0 failed**
(85 minutes, slowed by everything else running). Real Chrome against the
local API, as each of the six roles opening **every** sidebar and More item (the acceptance criterion):
**0 refused (4xx) calls in every session and no permission-error text** (the earlier audit had 1-12 per
item for `procurement`, `site_engineer` and `ca_tax`); Team & Access (both tabs) and PM's Master Settings
need no sideways scroll at 375, 414, 768 and 1280px; PM's Master Settings showed all 29 settings with 0
Edit buttons and none of the write controls, while the Director's showed 31 Edit buttons and every write
control and no longer has the two team tabs.

**Deployed to production in three steps, 25 September 2026.** (1) **Backend, `b77a46c` (Part A):** the
first attempt shipped nothing -- `git pull` had not been run, the server was still at `54ff6a0` -- found
because production's OpenAPI still had no `/role-permissions` (404); redone with the pull, it lists
`/role-permissions` (205 paths, was 204) with its response schemas, and an anonymous call answers 401.
(2) **Frontend, `45172de` (Part B):** the served bundle changed from `index-BPfOBPdb.js` to
`index-D-BkS1ab.js`; downloaded from production it contains the Team & Access screen, the
`/role-permissions` request, the PM read-only line and "Open to every role", and no longer contains the
hand-kept permissions text or the "Dashboard summary only" CA/Tax note. (3) **Frontend, `6bba458`
(handbook wording):** two redeploys before the merge fetched nothing new ("Already up to date") and
changed nothing; after the merge the bundle changed to `index-BfhevSxH.js`, which contains "Team &
Access > People" and "Team & Access > Roles & permissions" and none of the old "Master Settings > User
Management" wording.

**Open items -- not verified or not done:**
- *No logged-in click-through on production.* The Director's live Roles & permissions data and PM's
  read-only Master Settings were checked only against the local database; production was checked from
  what it serves (bundle contents, OpenAPI, anonymous 401s).
- *The generator reads a FastAPI-internal API.* Included routers are stored as `_IncludedRouter` and
  read through `effective_route_contexts()`; a FastAPI upgrade that changes it would break the endpoint.
  The tests compare it with OpenAPI and pin known gates, so an upgrade fails in CI, not silently on the
  Director's screen.
- *Labels are the route function's name, humanised* ("Create project"); a few read awkwardly and
  `LABEL_OVERRIDES` in `role_permissions.py` is empty until someone curates it.
- *The navigation table is hand-written* (`navAccess.js`, each row naming its endpoints); it follows the
  API, and the Director's new screen is the way to re-check it, but nothing tests it automatically.
- *Sports & Scope for PM and Reports for `sales`* were confirmed only by the zero-refused-calls audit
  on the local database; a role-specific empty state was not separately inspected.
- *The Help handbook was wrong until #199* (found late; see above). Other Help text was not re-audited
  against the new navigation beyond the strings that named the moved screens.
- *Still open from Amendment 48's audit:* the More-group placement decisions (where Vendor, Tools,
  Reports, Admin and Education live -- deliberately out of scope here), global quick search, Section C
  quotation content, and HTTPS on a proper domain. Director review of the new screen, and of the
  Quotations and Payments screens, is pending; nothing has been tested on a real phone (the site is
  still plain HTTP on a bare IP).
- *Test data:* the extra test users (`audit-site_engineer@`, `audit-ca_tax@`) exist in the local
  development database only; nothing was created in production.

### Amendment No. 52 — Placement of the "More" Group (Vendor, Tools, Reports, Admin, Education, Help)
**Registered 25 September 2026**, on the Director's instruction to register and spec the placement
decisions Amendment 48's audit left open and Amendment 51 deliberately did not take (it made every
More item role-accurate where it is). Grounded against current code:
- **The eight headers are done; everything else is still in the temporary "More" accordion.**
  Amendment 36 (Phase 1) parked Vendor, Tools, Reports, Admin and Education there "pending the Phase 8
  placement decision" (`Sidebar.jsx` comment); plan E.1 still lists all of them "needs a decision"
  and no such decision was ever signed off.
- **Help is filed under "Admin"** (`MORE_GROUPS`), the group whose other items are `pm`/`director`
  only -- the one item open to every role, in the menu a Sales rep has no reason to open (plan
  mismatch #3, still open). **Education** is a one-item group of its own although the plan describes
  it as a standalone link.
- **The groups are mostly one or two items.** Vendor: 1 (Vendor Master). Reports: 1. Education: 1.
  Tools: 4. Admin: 6. Every item costs three taps -- More, the group, the item -- and for a Sales
  rep (whose whole More is a calculator, Reports and Help) that is most of the menu.
- **"All Quotations" in Admin is a duplicate.** It calls `handleDrillDown("quotations_admin", {})`,
  the same call the Quotations header makes, and opens the same screen; since Amendment 49 the header
  is open to `sales`/`pm`/`director`, so the Admin entry adds nothing.
- **Reports does not tell Sales what it can generate** (plan mismatch #4): the Type selector lists only
  Quotation Pipeline for Sales, with no note that Margin Performance (`pm`/`director`) and Override
  Summary (`director`) exist.
- **The Help handbook is out of step in places.** `handbookData.js` entry "All Quotations" still
  describes a Director-only register, although Amendment 49 opened the Quotations list to Sales and PM;
  and Amendment 51's own miss (the handbook still naming Master Settings for user management, fixed in
  #199) shows the location text has to be searched for whenever a screen moves.
- **Resolved already:** Estimates (plan mismatch #2) is now the second tab of the Quotations screen
  (Amendment 49), so it needs no entry of its own.
Needs a Director-approved spec before implementation, per this register's own Change Process
(spec: `docs/annexures/Section-56-specs.md`, awaiting approval).

## Register Notes (non-software, business-process)

**Note R1 — Rate validation**: Validate the estimation engine against FY 23–24 actuals
(projects file on record): recreate one or two past projects in the app, compare totals
against real costs, tune rate tables where they diverge. Prerequisite for trusting every
quotation the app produces.

**Implemented 13 September 2026 — starter rate card:** a review of 23 real historical
NestaPrime quotations (2021-2026) produced 20 clean, isolable ₹/unit rates (civil base
prep, PP tile/wood/PVC/turf/EPDM flooring, SS railing, chain-link fencing, badminton pole
equipment) seeded into `RateItem` as Manual/unverified entries (`backend/scripts/
seed_rate_items.py`) — nothing here drives a real quotation until a PM/Director confirms
each one from the Rate Sheet screen (J.1's own rule). HSN/SAC codes and GST% were sourced
from CBIC's official service/goods classification (Notification 11/2017-CT(Rate)) and the
September 2025 GST 2.0 rate notifications, not guessed. Three categories (asphalt
sub-base, surface repair/prep, acrylic/synthetic court coating — the last being the most-
used flooring type in the sample) are parked pending accountant sign-off: no confident
official HSN/SAC match exists for them. Several more (LED floodlights, basketball/
volleyball equipment "sets", the prefab steel shed, swimming pool civil work, the pool
filtration 35%-of-civil formula, and the 84%-of-MRP equipment margin) were left out
entirely rather than forced into a per-unit rate they don't actually have in the source
data.

This review also surfaced a real billing-accuracy gap, fixed as part of the same work:
HSN 9506 sports-goods equipment is 5% GST under GST 2.0, not the flat 18% the app applied
everywhere via one Master Settings value. `RateItem` now carries an optional per-item
`gst_percent` override; Estimate pricing and real Quotation `gst_amount`/`quotation_total`
both blend each sport's own cost-sheet lines into a cost-weighted effective rate instead
of the flat global one (`app/api/pricing.py::effective_gst_rate_percent` /
`cost_weighted_gst_rate_percent`) — a sport with no lines yet still falls back to the
unchanged flat rate.

**Completed 14 September 2026 — recreate & compare:** "Recreate a past project and
compare totals" (this Note's original scope) is now done. Two real, closed FY 22–23
projects were rebuilt end-to-end in the live app (Project Setup → Cost Sheet → Estimate →
Quotation), sourced from the accounts team's own project-wise expense workbook, both
Government clients (Tender Mode auto-on per B.2):

- **Indian Army, Mathura — outdoor Basketball court.** Real accounts: material ₹8,93,169 +
  labour ₹1,84,267 + site logistics ₹76,698 = ₹11,54,134 cost; sold at ₹12,96,610 (ex-GST,
  **11.0% margin** — below the app's own 12% Government floor); ₹15,30,000 incl. GST.
  Recreated as Manual Lines split into material-only rates with an explicit labour
  category per line (Civil/base/site prep, MS fabrication & erection, Acrylic/PU, Turf
  laying, Electrical) rather than one blended amount, so each category's assumed % could
  be checked individually — the site-logistics ₹76,698 was deliberately left out of the
  lines since K.1's own 6% site-establishment step already models that layer. App-computed
  cost sheet: **₹14,63,408.06** (+26.8% / ₹3,09,274 over real cost — company overhead
  recovery 10%, DLP reserve 1%, BOCW cess 1%, per-package contingency, and a ₹50,000
  Government-only structural sign-off line (E.5) the real project never itemized, on top
  of the labour-% divergences below). Quotation at the policy target margin (15% —
  Government floor 12% + 3% competitive gap): **₹20,31,554.72 incl. GST**, +32.8% /
  ₹5,01,554.72 over the real ₹15,30,000.
- **NHAI, Noida — Badminton PU court.** Real accounts: ₹4,63,786.50 cost; sold at
  ₹6,01,594 (ex-GST, **22.9% margin** — well above the app's 15% target); ₹7,10,000 incl.
  GST. Recreated as one material-only Manual Line (PU flooring, Acrylic/PU labour
  category). App-computed cost sheet: **₹6,05,320.56** (+30.5% / ₹1,41,534.06 over real,
  same overhead-layer causes as above, no structural sign-off line this time as it's a
  smaller building-status). Quotation at the same 15% target margin: **₹8,40,327.37 incl.
  GST**, +18.4% / ₹1,30,327.37 over the real ₹7,10,000.

**What diverges and what it means:**
1. **Margin policy vs. real outcomes.** The app applies one flat 15% target to every
   competitive-segment Government client regardless of project. Real margins on these two
   varied enormously (11.0% vs. 22.9%) — Mathura's real price was actually *below* the
   app's own 12% floor, meaning the app would never have let that historical deal through
   at the price it was actually won at. This is a policy question for the Director, not a
   bug: either the floor is right and that 2022 deal was underpriced, or the floor is set
   too high for competitive Government bids of this kind.
2. **Labour-category % assumptions, checked against Mathura's real split:** Civil/base/site
   prep assumed 30% vs. 21.85% real (too high); MS fabrication & erection assumed 22% vs.
   6.4% real for basketball-pole *installation* specifically (likely fine for genuine
   fabrication work, too high for installing a pre-fabricated pole+board set — these may
   need splitting into two categories); Acrylic/PU assumed 20% vs. 22.7% real (close);
   Turf laying assumed 12% vs. 25.4% real (assumption roughly half of real — the largest
   gap found); Electrical assumed 25% vs. 31.4% real (somewhat low). Site-establishment's
   flat 6% landed close to Mathura's real ~6.6% logistics ratio — no change indicated
   there.
3. **Rate-table gaps, independently reconfirmed.** Neither project could be built with a
   seeded `RateItem` rate — asphalt base, acrylic/PU court coating, and basketball
   pole+board equipment all had to go through Manual Line, exactly the three categories
   the 13 September rate-card review already parked pending accountant sign-off. Two
   independent data sources (23 historical quotations, and now these two full project
   rebuilds) agree on the same gap.
4. **The ₹50,000 structural sign-off line (E.5)** has no line-item equivalent in either
   real project's accounts — a genuine, disclosed difference in scope between what the
   app now requires for Government/Tender work and what was actually billed in 2022–23,
   not a computation error.

No rate-table or percentage change has been made off the back of this alone — per Annexure
2's own Change Process, any resulting tuning (labour-category %, the margin floor, or
adding the three parked rates once sign-off exists) needs its own Director-approved spec
before implementation.

**Additional validation — Bathinda, 15 September 2026 (Amendment 11 Part B2's own
follow-up):** recreated a third real project, "Badminton Shed Construction, Bhatinda"
(private/commercial client — no client identity was recorded in the source accounts,
unlike Mathura/Noida's named Government clients), from the same expense workbook.
Bathinda's accounts are structurally different from Mathura/Noida: costs are recorded as
**all-in contractor payments** (material and labour bundled per vendor) rather than
separately itemized Material/Labour line pairs — a genuine, disclosed limitation. Most
lines couldn't be split into a clean material-only Manual Line rate without either
fabricating a split or accepting a known labour double-count (a Manual Line's rate is
always treated as material-only, with the app adding its own labour % on top); one line
(₹2,78,194, an explicitly-labelled "Civil + Labour" contractor payment) was entered as-is
with this double-counting risk flagged, and two smaller electrical-adjacent lines carry
the same lower-confidence risk (one of them itself contaminated with unrelated "glass
door" scope).

One genuinely clean comparison did emerge: Shakir Labour Charges (₹1,72,300, pure
labour) against the steel structure material (Garg Steel + Suraj Steel, ₹7,06,904) gives
a real MS fabrication & erection ratio of **24.4%** — close to the 22% default, and a
useful second, independent confirmation that 22% is reasonably calibrated for genuine
erection/fabrication work, as distinct from the 6.4% pre-fab-*installation* ratio
Mathura's basketball pole found (exactly why Amendment 11 Part B1 split that into its
own category rather than moving 22%).

App-computed cost: ₹17,00,570.07 (+32.55% / ₹4,17,578.07 over real ₹12,82,992) — higher
than Mathura (+26.8%) and Noida (+30.5%), consistent with the known double-counting on
the mixed-category lines on top of the usual overhead-layer markup. App-computed
quotation total (Standard package, Corporate client type, Tender Mode off, GST-inclusive):
₹24,47,161.81 at an 18.0% margin, vs. real ₹17,71,000 at a 14.5% real margin (+38.2% /
₹6,76,161.81 over real).

No turf-heavy or cleanly-itemized-electrical project was found among this workbook's
remaining sheets (Shishukunj is pure accessories procurement with no labour split at
all), so **Turf laying's 12%-vs-25.4% gap remains the largest unvalidated finding** —
still open per Part B2, pending a future project with genuinely separated
material/labour accounts. No rate-table or percentage change has been made off the back
of this addendum either, same Change Process discipline as above.

**Turf validation attempt, 15 September 2026 -- no usable data found.** Searched for a
real turf project's actual expense breakdown to close the gap above. Neither
"Turf Ujjain.xlsx" (the path first given) nor "Turf Cost Sheet.pdf/docx" (a payment-
receipt tracker for a different, unrelated "Indore Turf Project" -- dates and amounts
received from the client, no cost breakdown at all) existed or helped. One file,
"Cricket_Turf_Spec_BOQ_Corrected.docx", does contain a full line-item cost breakdown for
a cricket turf build -- but it is explicitly an *indicative market-rate estimate*
("budgetary... based on current Tier-2-city wholesale/contractor pricing... not a
substitute for vendor quotations," per its own disclaimer), not a real project's actual
accounts, so it was **not used** -- treating it as real data would have broken the same
"never fabricate numbers" discipline this whole exercise depends on. Turf laying's gap
stays unvalidated; closing it needs a genuine historical project's real cost records,
not a market-rate estimate, whenever one surfaces.

**Note R2 — Backup & restore drill**: Quarterly: restore a Lightsail snapshot to a test
instance and confirm app + data return correctly. A backup never restored is a hope, not
a backup.

**Infrastructure in place (13 September 2026):** the existing Lightsail auto-snapshot
doesn't quiesce Postgres first, so a real `pg_dump` was added alongside it (Director
decision, 13 Sept: add the consistent backup, then drill that, rather than drilling a
snapshot with a known mid-write risk). `deploy/backup_db.sh` (nightly cron, gzip,
integrity-checked, 14-dump retention) and `deploy/restore_drill.sh` (an isolated,
throwaway-container restore + row-count sanity check, safe to run anytime) — see
[`deploy/README.md`](../../deploy/README.md#backups--restore-drill-note-r2) for the full
runbook, both halves of the quarterly drill (pg_dump + the Lightsail instance-snapshot
restore), and [`docs/ops/restore-drill-log.md`](../ops/restore-drill-log.md) for the
recurring record. Both scripts verified locally against a real dump of the dev database
(13 September 2026 → every table restored with its original row counts intact,
`users`/`sports` non-empty) — this "Ongoing" item stays open by nature (it recurs every
quarter), but the
capability to actually run it, and prove it was run, is now real rather than aspirational.

**Note R3 — Launch-night housekeeping (closed 13 September 2026)**: Two items from the
original post-launch punch list were never formally closed out. Both are now resolved.

(1) **Closed (13 September 2026).** The placeholder/test account from setup --
`agent-temp@nestaprime.com`, a *Director*-role account created 12 September -- has been
deactivated in production (`is_active = False`). Confirmed live-tested first: logging
into it correctly hit the app's own forced-password-change gate rather than granting
access outright, which is what actually surfaced that this account still had a shared,
Director-assigned password sitting active in production -- worth deactivating on that
basis alone, independent of it being a leftover test account.

(2) **Confirmed closed (13 Sept code check).** `distance_km`'s bound validation lives
on the single shared `ProjectCreate` schema (`backend/app/api/projects.py`) that both
Quick-mode (`handleQuickSubmit`) and Detailed-mode (`handleSubmit`) submit through in
`frontend/src/ProjectSetup.jsx` — there is no separate Quick-mode schema that could
have missed the fix. Quick mode simply never populates `distance_km` (defaults to
`None`, which the `ge=0, le=99999.9` bound accepts); Detailed mode sends it as a real
number and is validated by the same bound before it reaches Postgres. One schema, one
fix, both paths covered.

## 3. Priority & Sequencing (Recommended)

No calendar commitment (no "Week N" deadlines) -- work proceeds in small sections, each
shipped through the full branch → PR → tests → merge → deploy cycle before the next
starts. The order below is the priority, not a schedule.

**Superseded, kept for the historical record (v1.11 reconciliation):** the actual build
order (PRs #23–#47, 12–14 September) shipped every section below out of order relative
to this table — Section 7 (cross-sell) and Section 8 (integrations) landed *before*
Section 6 (customizable fields + vendor master), for example. All eight sections are now
implemented (see the Amendment entries above for exact status and gaps), except Note R2's
restore drill, which is ongoing by design. This table is left as-is rather than rewritten
to match what actually happened.

| Section | Amendments / Notes | Why this order |
|---|---|---|
| 1 | No. 2 + No. 4 (form + dashboard/guided) | Makes the app USABLE daily |
| 2 | No. 9 (court sizing) — quick win | Small change, immediate flexibility |
| 3 | Note R1: rate validation | Makes the numbers TRUSTWORTHY |
| 4 | No. 1 (branding) + No. 10 (handbook quick-start card) | Beautiful + team can start |
| 5 | No. 10 full handbook + No. 6a/6c (rights + reports) | Team trained; control and oversight |
| 6 | No. 5 (customizable fields) + No. 7 (vendor master) | Flexibility + procurement bridge |
| 7 | No. 3 (cross-sell) | Revenue multiplier once flow is right |
| 8 | No. 8 (integrations) | Investigate wa-gateway first |
| Ongoing | Note R2: restore drill | Data safety, recurring regardless of build sequence |

## Parking Lot

New ideas raised after the v1.9 freeze, held here per the Register Freeze Rule (Part 1)
until reviewed at the next wave's completion -- not approved, not scheduled, not
implemented.

*(Empty as of v1.10 — the item raised 12 September, "Amendment No. 5 (Customizable
Fields)" / dropdown "Others" + Custom Notes, has been reconciled by Director decision:
merged into Amendment No. 5's own scope above, not registered as a separate
amendment. See Amendment No. 5.)*

## 4. Approval

Amendments 1–5: ☐ Approved ☐ Changes ☐ Later
Amendments 6–10: ☐ Approved ☐ Changes ☐ Later
Notes R1–R2: ☐ Noted

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 11 September 2026
