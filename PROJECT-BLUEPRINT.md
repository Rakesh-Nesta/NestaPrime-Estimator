# NestaPrime Estimator — Project Blueprint & History (Master Reference)

**Purpose of this file:** a single, self-contained document of what this app is, how it's
built, and everything done to it so far. Attach this file to any new session (this repo
or elsewhere) to bring it up to speed without re-explaining the project. Last updated:
22 September 2026, current through Amendment No. 35.

---

## 1. What this app is

NestaPrime Estimator is a pre-sales quotation and lead-tracking tool built for **NestaPrime
Sports Infrastructure**, a company that builds/resurfaces sports facilities (courts, turf,
flooring, structures) for schools, corporates, government/tender clients, and individuals.

**Governing philosophy (from the original blueprint, Annexure-2.md Part 0):** the app
serves one conversation — what the client HAS -> what he WANTS -> the NPS solution -> the
PRICE -> cross-sell. Ultimate goal: "the app's purpose is to be fully customizable to meet
specific business requirements." Every change made to this app, before or after launch,
is measured against that.

**Origin:** built from a formal design-phase blueprint package
(`docs/NPS_FINAL_NestaPrime_Estimator_Package_2026-09-04.zip`), whose internal section
references (Part O, M.1-M.7, K.1-K.4, B.1, J.1, P.2, etc.) are cited throughout this
project's own documentation as the normative source. `docs/audit-closure.md` records the
original gap-by-gap closure audit against that blueprint (19 ranked gaps, all closed by
launch). This file does not repeat that audit — see `docs/audit-closure.md` and
`README.md` for it.

**Deployed to production** 11 September 2026 (AWS Lightsail, `65.1.234.78`, repo at
`/home/ubuntu/NestaPrime-Estimator`). Every change since launch follows the formal change
process described in Section 3 below, logged in `docs/annexures/Annexure-2.md` and
`docs/ops/deploy-log.md`.

---

## 2. Stack & how to run it

- Backend: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL 15
- Frontend: React, Vite, Tailwind CSS
- Auth: JWT (argon2 password hashing), 6 fixed roles
- AI: Anthropic/Claude (`app/services/ai_content.py`) for cover notes, message drafts,
  report summaries, the Education chat assistant, and Sport Build Guide construction
  sequences — always human-reviewed before save/send, never auto-sent
- Messaging: WhatsApp (self-hosted `wa-gateway`), Telegram (Bot API), Email (SMTP,
  Google Workspace) — all three are real, live send channels in production
- Backups: nightly `pg_dump` (gzip, 14-dump retention) + quarterly restore drill, both
  live-verified (`deploy/README.md`, `docs/ops/restore-drill-log.md`)

Full local run instructions: `README.md`.

---

## 3. The domain model — how a job actually flows through the app

### 3.1 The document chain (Part M.1)

```
Client  ->  Project  ->  Cost Sheet  ->  Estimate  ->  Quotation  ->  (Won)  ->  Work Order
                            |                |             |
                     internal cost    client-facing    the single,
                     build-up, PM/    RANGE per sport   FROZEN, firm
                     Director only    x package, multi- price for the
                     (K.3)            option ("the      approved subset
                                      menu")            ("the bill")
```

- **Cost Sheet** (Stage 1) — the internal, take-off-based cost build (materials, labour,
  site establishment %, overhead %, contingency %). Must be **Verified** before an
  Estimate can be created. PM/Director only (`COST_ROLES = ("pm", "director")`).
- **Estimate** (Stage 2) — client-facing, but exploratory: one or more **options**
  (Budget/Standard/Premium) per sport, each a **price range** (`price_low`-`price_high`,
  +/-5% around the target-margin selling price). The client reacts per option: approved /
  rejected / "demand" (wants changes). `cost_for_option` is PM/Director-only (K.3, Sales
  never sees it).
- **Quotation** (Stage 3) — cannot be created until the Estimate shows at least one
  client-approved/demanded option. Covers only that approved subset of sports. Values
  **freeze at creation** — no re-pricing step after. This is the single firm number the
  client actually receives.
- **Work Order** — created once a Quotation is Won. Tracks award status
  (Awarded/In progress/Completed) and milestone payments received
  (`WorkOrderPaymentEntry`: milestone name, amount received, date, GST-TDS if
  government/PSU-withheld). This already exists — payment *reconciliation* (money
  actually received) is tracked; payment *scheduling/due-dates/reminders* (money
  expected) is not, as of Amendment 35 — see Section 6.

Two supplementary, project-level records exist alongside this chain but don't gate it:
**Scope Checklist** (which scope items apply, 30-item checklist) and **Site Survey**
(on-site conditions, photo evidence, `MIN_PHOTOS_TO_COMPLETE = 4` to mark it done).

### 3.2 Roles (`backend/app/models/user.py`, the 6 fixed roles)

| Role | Core access |
|---|---|
| `sales` | Create projects, client communication, record client responses on Estimates/Quotations, send messages. **Never sees cost/margin figures (K.3).** Cannot create Cost Sheets or Estimates. |
| `pm` | Everything Sales has, plus Cost Sheet/Estimate creation, Rate Sheet, Price Calculator, Vendor/Procurement access, most Reports. |
| `director` | Full access — the only role for Master Settings, Audit Log, Cross-Sell Admin, All Quotations (unfiltered), Client blacklist/overdue flags, User Management. |
| `procurement` | Vendor Master, Price Requests, Purchase Orders. |
| `site_engineer` | Rate Sheet / pricing tools access (same tier as PM/Director/Procurement for those specific screens); site-level work. |
| `ca_tax` | Accounting/tax-adjacent role (GST-TDS, compliance figures) — narrowest documented footprint of the six. |

**K.3** (the recurring shorthand throughout this project's docs): cost and margin figures
are never shown to Sales — enforced server-side, not just hidden in the UI.

### 3.3 Pricing & GST rules worth knowing (K.1-K.4)

- GST is **not flat 18% globally** — it's Director-configurable per Master Setting, and
  blends a 5% rate for HSN-9506 sports-equipment lines against 18%-rated civil/flooring
  work on the same Cost Sheet (`cost_weighted_gst_rate_percent`). Quotation PDFs and
  Billing Handoff back-derive the printed rate label from the document's own frozen GST
  amount, never a live re-query (Amendment 24).
- Margin policy is per client-type (School/College/Housing Society/Corporate/Club/
  Government-Tender/Individual), tunable from Master Settings, with a Government floor
  margin.
- Master Settings values can be overridden per-document (`Override` model);
  three-tier precedence is **document Override > current Master Setting > hardcoded
  Python default constant**. Many K.1 cost constants (e.g. site establishment %,
  contingency %) run purely on their hardcoded default with no Settings row ever
  required — this matters if you're ever asked to validate or reject a `setting_key`
  (see Amendment 32).
- Every numeric Setting/Override parse goes through `settings_parse.py::parse_setting_number`
  (Amendment 22) — a bad value fails clearly at write/read time, not as a bare 500.

---

## 4. Governance — the change process every amendment follows

Source of truth: `docs/annexures/Annexure-2.md`.

1. **Record** — a change or gap is written into the Annexure-2.md register, with
   file:line evidence, before anything is built.
2. **Director approves** — a full spec doc is prepared (`docs/annexures/Section-N-specs.md`),
   covering current state, proposed spec, acceptance criteria, and any open decisions with
   proposed defaults. Nothing is built until the Director explicitly approves the spec
   (per-item, never assumed from a prior approval).
3. **Implement** — branch -> PR -> tests -> merge, each PR gets a fresh, explicit merge
   authorization from the Director ("merge N once it's green").
4. **Deploy** — every production deploy is logged in `docs/ops/deploy-log.md`, generally
   the same day as merge, and live-verified against real production data/endpoints before
   being marked closed in the Annexure-2.md entry.

**Register Freeze Rule:** no new amendments outside a formal register update; new ideas
go to a Parking Lot until reviewed.

**Self-identified amendments:** since 19 September 2026, most new amendments have come
from proactive, Director-requested gap audits (7 run so far) rather than only Director
observations — each audit's findings are independently spot-verified against live code
before being registered, not taken on faith.

---

## 5. Complete amendment history (1-35, all CLOSED unless noted)

| # | Title | One-line outcome |
|---|---|---|
| 1 | Brand-Themed and Animated UI | Dark theme, gold `#c9a227` accent, animated court diagrams, 0.2-0.3s motion. |
| 2 | Simplified New Project Setup Form | Quick/Detailed modes; Quick mode now correctly routes through Sport Selection for dimension entry. |
| 3 | "Complete Your Facility" Cross-Sell | Up to 5 sport-matched add-ons at the Estimate step, one-tap, never forced, cost/margin hidden from Sales. |
| 4 | Main Dashboard + Guided Navigation | Business-summary dashboard, logout control, project browse/resume, per-client project list, Admin/user nav separation. |
| 5 | Customizable Forms (field governance) | Director-controlled compulsory/optional/hidden on 6 fields (`GOVERNED_FIELD_KEYS`); "Others" dropdown rule on Category/Vendor/City/District; Custom Notes on Project/Cost Sheet/Estimate. |
| 6 | User Rights + Reporting & Oversight | Read-only role-permissions viewer; Director cross-project quotation browse + CSV/PDF export; period-preset Reports. |
| 7 | Vendor & Product Master | Vendor codes, per-vendor Product catalog with approx pricing; feeds Rate Sheet indirectly via Price Request replies. |
| 8 | WhatsApp/Email/Telegram Messaging | All three channels real and live in production (self-hosted wa-gateway, Bot API, Google Workspace SMTP), delivery status tracked where the provider supports it. |
| 9 | Flexible Court Sizing | Per-project size override with federation-minimum floor; Director-editable baseline standard sizes via Sports & Scope Admin. |
| 10 | User Handbook | Quick Start card + 19-chapter full handbook, Estimator/Director guides, 20-question FAQ, Hindi/Hinglish terms, kept current through Section 19. |
| 11 | Rate Card & Margin Tuning | 3 parked rate-table gaps seeded as `rate=null` catalog rows; new "Equipment installation (pre-fab)" 8% labour category split from a 22%-vs-6.4% real gap. |
| 12 | Dashboard Drill-Down & Nav Restructure | Every dashboard tile drills into a real filtered list; nav regrouped into Dashboard/Quotation/Projects/Client/Vendor/Tools/Reports/Admin/Education. |
| 13 | AI-Assisted Content | `ai_content.py` (Anthropic) powers Quotation cover notes, message drafts, report summaries — always human-reviewed, never auto-sent. |
| 14 | Customizable Document Templates | Director-editable company details + Quotation T&C/warranty from Master Settings; Reference Images embedding in Quotation PDFs. |
| 15 | Education Tab AI Assistant | Chat assistant grounded only in the handbook (no live app data, no guessing) via the same Anthropic integration. |
| 16 | Sport Build Guide | Structured per-sport build reference (accessories/flooring/package tiers) assembled from existing verified data; Part 2 added AI-drafted, Director-reviewed construction sequences. |
| 17 | Export Sanitization (CSV/XLSX injection) | `sanitize_row` neutralizes formula-injection payloads at 10 export sites, storage/display unaffected. |
| 18 | Login Rate Limiting | 5 failed attempts locks an account 15 minutes; unknown emails never count toward lockout. |
| 19 | Structure Form Crash Fix | Fixed a null-recommendation crash in Cost Sheet Builder's Structure take-off form. |
| 20 | PO Receiving Race Fix | Receiving now requires the expected prior value (409 on mismatch) instead of silently overwriting; status correctly reverts on correction. |
| 21 | Double-Submit Guard | All 21 Cost Sheet take-off forms now disable their submit button during save. |
| 22 | Settings/Override Validation | Numeric Settings/Overrides now validated at write time with clear errors; GST divisor guarded against `<= -100`. |
| 23 | Document/PO Number Race Fix | Collision-and-retry wrapper for project/PO number generation under concurrent creation. |
| 24 | False "18% Flat" GST Label Fix | Quotation PDF and Billing Handoff now back-derive the printed GST rate from the document's own frozen amount. |
| 25 | Rate Sheet Import Field-Drop Fix | Non-rate field edits (vendor, HSN/SAC, etc.) from an Excel import now apply even when the rate cell is unchanged. |
| 26 | Re-Creating Estimate/Quotation Crash Fix | Fresh document numbering now computes the next real revision instead of hardcoding `1`; re-bidding a Lost project works. |
| 27 | Vendor Reply GST-Basis Fix | An "incl. GST" vendor reply is now correctly converted to ex-GST before being applied to the Rate Master/Cost Sheet. |
| 28 | Dashboard "Open Projects" Fix | A project only counts as closed when *every* Quotation on it is Won/Lost; added `Project.is_calibration` to exclude validation data from all dashboard tiles. |
| 29 | Client Flag Audit Trail | Blacklist/overdue flag changes now write an audit log entry, matching the existing consent-change pattern. |
| 30 | Report Release Audit Trail | Report release now audit-logged, matching the existing Quotation-release pattern. |
| 31 | Client Signatory Audit Trail | Signatory create/update now audit-logged. |
| 32 | Master Settings Override Guard Fix | Numeric-guard bypass closed; narrowed mid-implementation (Director-approved) after discovering many K.1 constants legitimately have no Settings row at all. |
| 33 | Skip Request Reject Path | Added `REJECTED` status + reason, closing a deadlock where a rejected-but-unrecorded skip request permanently blocked the project. |
| 34 | Vendor Deactivation + Duplicate Guard | `Vendor.is_active` (retire, don't delete); duplicate name/GSTIN now rejected with `409`. |
| 35 | Site Survey Forward Navigation | **Spec approved, not yet implemented** — see Section 7 below; adds a "Next ->" button routing to Documents, matching Scope Checklist's own destination. |

Full detail, file:line evidence, and live-verification notes for every entry above:
`docs/annexures/Annexure-2.md`. Individual approved specs: `docs/annexures/Section-N-specs.md`.

---

## 6. Current state — what exists that a CRM-style ask might assume is missing

Checked directly against the schema on 22 September 2026, because it's a common wrong
assumption when comparing this app to a polished dashboard mockup:

**Already real and production-hardened — do not rebuild:**
- Real Postgres DB, JWT auth with login lockout (Amendment 18)
- 6 real roles with granular server-side gates (not just UI hiding)
- Document/PDF storage (`Attachment` model)
- Verified nightly backups + quarterly restore drills
- Full audit log (used throughout Amendments 29-31)
- WhatsApp/Telegram/Email sending, already wired into the Quotation document screen
  (`MessagesPanel.jsx`), already available to Sales
- Payment *reconciliation* — `WorkOrder` + `WorkOrderPaymentEntry` already record
  milestone payments received, with GST-TDS, once a project is Won

**Genuinely missing, confirmed by direct check:**
- No pre-project "Lead/Opportunity" entity — `Project` (with full technical fields) is
  the earliest record today; nothing lighter-weight exists for an early-stage enquiry
- No sales-pipeline stage tracking separate from the document workflow
- No follow-up/reminder field or mechanism anywhere (`Client` has none)
- No forward-looking payment due-dates/reminders (only backward-looking `amount_received`)
- No global quick search (search exists only inside `AllProjects`/`AllEstimates`/
  `AllQuotations`, and the last is Director-only in the nav)
- **Estimate has no nav header of its own** — only reachable via a Dashboard tile,
  unlike Quotation which gets a full dropdown — likely the root of any Quotation-vs-
  Estimate confusion

---

## 7. Open / in-progress items — not yet amendments, or approved but not built

As of 22 September 2026:

- **Amendment 35 (Site Survey Next button)** — spec approved-pending, not yet implemented.
- **Written plan document** — `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`
  is a live DRAFT (not an Annexure 2 Amendment) covering: 5 Sales-rep UX findings, 3
  verified Sales-rep capability gaps (follow-up tracking, my-open-items view, global
  search), quotation-descriptiveness (richer AI cover letter + descriptive non-priced
  scope-of-work + configurable T&C/bank details, lump-sum pricing preserved by explicit
  Director instruction), a dashboard redesign + nav-shell (top vs. sidebar) decision
  still pending a second reference option, and a full header-by-header meaning audit.
- **CRM-lite direction under discussion, not yet specced** — a lightweight `Opportunity`
  entity with its own pipeline stage (New enquiry -> Contacted -> Site assessment ->
  Estimate prep -> Quotation sent -> Negotiation -> Won/Lost), kept deliberately separate
  from Project/construction progress, plus extending `WorkOrderPaymentEntry` with
  forward-looking due-dates. Assessed as feasible and additive (no rewrite of existing
  Client/Project/Quotation chain needed), sequenced after the Sales-bottleneck items
  above since those are cheaper and higher-leverage per the Director's stated priority:
  *"my hole point round to sales persons or his actual bottle neck."*
- **Four nav-label mismatches surfaced, not yet approved for fixing:** "New Quotation"
  and "Create Cost Sheet of Quotations" are the same action under two wrong labels;
  Estimate has no header (see Section 6); "Help" sits inside the Director-only-feeling
  "Admin" menu; Reports silently narrows for Sales with no on-screen explanation.

---

*Maintained alongside `docs/annexures/Annexure-2.md` (the governing register — always the
source of truth on amendment detail) and `docs/planning/` (pre-amendment planning docs).
Prepared by: R. Patni (with AI development assistance) | Last updated: 22 September 2026.*
