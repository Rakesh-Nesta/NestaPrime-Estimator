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

### Amendment No. 9 — Flexible Court Sizing
Standard sizes become configurable suggestions per sport — adjustable smaller/larger per
project; admin-editable (links to No. 5).

**Implemented 12 September 2026 (PR #24):** `SportSelection.jsx`'s `CourtSize` accepts
the standard size with one click or reveals L/W inputs via "Customize size," floored
server-side at federation playing dimensions. **Nuance:** per-project override is
confirmed; a separate Master Settings control letting the Director edit the *baseline*
standard suggestion itself (as opposed to a project's override of it) wasn't found.

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
v2) — this is the largest gap found in this reconciliation pass:** `Help.jsx` +
`handbookData.js` deliver the Quick Start card, a 12-screen full handbook, separate
Estimator/Director guides, and an FAQ with exactly the spec'd 20 questions, reachable via
an in-app Help button, with a browser print/save-as-PDF option. **Gaps:** (1) Hindi terms
are entirely absent, despite the spec explicitly calling for them; (2) the maintenance
rule this amendment itself sets — "every shipped amendment wave updates the relevant
chapter" — has not been followed since PR #34: Amendments 11, 12, and 13 (14–16
September) all shipped without any handbook update, so the handbook's 12-screen list is
now missing All Quotations, Vendors Admin, Messages Panel, Price Requests, Purchase
Orders, and Cross-Sell Admin. Bringing the handbook current is real, undone work — not a
documentation-only fix like the rest of this reconciliation pass.

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
