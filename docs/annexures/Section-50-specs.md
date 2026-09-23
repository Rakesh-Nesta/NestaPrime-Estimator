# Section 50 — Amendment No. 44 Spec

## Amendment No. 44 — Opportunities (Header Index Step 5)

### Registered scope
Build the `Opportunity` entity -- pre-project leads/enquiries, distinct from `Client` --
with a pipeline-stage lifecycle, the mandatory-follow-up-date discipline, a quick-capture
"Add Enquiry" intake separate from "Add a client", and a hand-off into the existing New
Project Setup flow once Won. The largest single piece in the header-by-header build index
(Section E of `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`).

### Current state (file:line evidence)
- No `Opportunity` model, table, route, or frontend screen exists anywhere (grep for
  "Opportunity"/"enquiry"/"inquiry" across `backend/app` and `frontend/src` -- only hit is
  `client.py:74`'s own comment naming it as future work).
- `Client.type` (`backend/app/models/client.py:32`) is `nullable=False` -- no path exists
  to create a `Client` today without picking a type, confirming a raw lead can't cheaply
  become a `Client` row yet.
- `Project` (`backend/app/models/project.py:76-179`) requires many fields
  (`site_condition`, `building_status`, `unit_system`, `package`, `number_of_courts`, all
  `nullable=False`) no Lead would have -- a Won Opportunity cannot auto-create a Project.
- `frontend/src/ProjectSetup.jsx:99,168,212` already supports `form.existingClientId` --
  an existing hook point for pre-filling the client on New Project Setup.
- `created_by_id` (FK to `users.id`, `nullable=False`) is an established pattern already
  on `CostSheet`/`Estimate`/`Quotation` (`document.py:148,249,408`), `PriceRequest`,
  `PurchaseOrder`, `SiteSurvey`, `WorkOrder`. Reused here, doubling as the "owner" field
  Amendment 43 flagged as missing on `Client`.
- `mark_quotation_won`/`mark_quotation_lost` (`documents.py:2589-2640`) do not audit-log
  the status change itself -- this codebase's audit log is for governance-relevant facts,
  not routine workflow transitions (confirmed convention, followed here too).
- `QuotationStatus`/`EstimateStatus` (`document.py:39-85`) are the established
  `str, enum.Enum` lifecycle-enum shape; `OpportunityStage` follows it.
- `ClientsAdmin.jsx`'s `canCreateClient` gate (`sales`/`pm`/`director`) and `GET /clients`'
  read gate (adds `procurement`) are the established role pattern for this data --
  Opportunities follow the same split (write: sales/pm/director; read: +procurement).

### Proposed spec

**1. `Opportunity` model** (`backend/app/models/opportunity.py`, new file, matching the
one-model-per-file convention `client.py`/`project.py` already use):
- `id`, `client_id` (FK `clients.id`, **nullable** -- unset until linked to or created as
  a real `Client`), `lead_name` (String, required -- always present even with no
  `client_id`), `lead_phone`/`lead_email` (String, nullable).
- `stage`: `OpportunityStage` enum -- `NEW`, `CONTACTED`, `QUALIFIED`, `WON`, `LOST`.
  Default `NEW`.
- `next_follow_up_date` (Date, **`nullable=False`**) -- the one field on this entity that
  is mandatory, per the Director's decision. `follow_up_note` (String(200), nullable),
  matching `Client`'s own field naming from Amendment 42.
- `lost_reason` (String, nullable) -- same shape as `Quotation.won_lost_reason`, set only
  on transition to `LOST`.
- `project_id` (FK `projects.id`, nullable) -- set once "Start Project" (item 5 below) is
  used; lets Quotations trace back to the Opportunity that produced them (build index
  step 8), via `Project.opportunity_id`... see item 6.
- `created_by_id` (FK `users.id`, `nullable=False`), `created_at`.

**2. Mandatory-follow-up-date discipline, enforced at the API layer:**
- `POST /opportunities` (Add Enquiry) requires `next_follow_up_date` in the payload --
  cannot create an Opportunity without one, same as the Director's decision states.
- `PATCH /opportunities/{id}/stage` requires a new `next_follow_up_date` in the payload
  for any transition to `NEW`/`CONTACTED`/`QUALIFIED` -- the stage cannot change without
  setting a fresh (today-or-later) date. Transitions to `WON`/`LOST` are terminal and
  instead clear `next_follow_up_date` to null (no more follow-up needed on a closed
  Opportunity), matching how a `Client`'s own field can already be cleared.
- A separate `PATCH /opportunities/{id}/follow-up` (same shape as `Client`'s own
  Amendment-42 endpoint) lets a rep push the date out without changing stage -- this one
  still requires a non-null date (this endpoint cannot clear it; only a WON/LOST stage
  change can).
- "Enforced ... whenever an existing follow-up date passes": once `next_follow_up_date <
  today`, the Opportunity shows as overdue everywhere it's listed (Opportunities screen,
  Follow-ups screen, Dashboard), same red-overdue convention `ClientsAdmin.jsx` already
  uses -- there is no push notification (matches Amendment 43's explicit out-of-scope);
  the enforcement is that the record cannot be advanced to a non-terminal stage while
  leaving the date unset or in the past.

**3. Endpoints** (`backend/app/api/opportunities.py`, new router):
- `POST /opportunities` -- Add Enquiry. `lead_name` + `next_follow_up_date` required;
  `lead_phone`/`lead_email`/`client_id` (to link an already-known Client immediately)
  optional. Role: `sales`/`pm`/`director`.
- `GET /opportunities` -- list, optional `stage` and `relationship` (`lead` = `client_id`
  is null, `client` = set) query filters, matching the CRM reference's All/Leads/Clients
  tabs. Role: `sales`/`pm`/`director`/`procurement`.
- `PATCH /opportunities/{id}/stage` -- see item 2. Role: `sales`/`pm`/`director`.
- `PATCH /opportunities/{id}/follow-up` -- see item 2. Same role gate as `Client`'s own:
  `sales`/`pm`/`director`. Not audit-logged, matching `Client`'s own follow-up endpoint.
- `PATCH /opportunities/{id}/link-client` -- attach an existing `client_id` to a
  currently-lead-only Opportunity (does not create a new Client; that still goes through
  the existing "Add a client" form, then this endpoint links it). Role: `sales`/`pm`/
  `director`.

**4. "Add Enquiry" quick-capture UI** -- a new button on the Leads & Clients screen next
to "Add a client" (`ClientsAdmin.jsx`), opening a small form with just Name/Phone/Email +
a follow-up date picker (pre-filled to a sensible near-term default, e.g. +2 days, editable)
-- deliberately not the full Client form (type/GSTIN/payment terms), per the Design input.

**5. Opportunities screen** (new `Opportunities.jsx`, replacing the `ComingSoon`
placeholder at `App.jsx`'s `screen === "opportunities"`): list with All/Leads/Clients
relationship-filter tabs (matching the CRM reference), a stage badge per row, follow-up
date column (red if overdue), inline stage-change and follow-up-date controls (same
inline-edit pattern `FollowUps.jsx`/`ClientsAdmin.jsx` already use). A Won row gets a
"Start Project" action (see item 6); requires `client_id` to be set first -- if the
Opportunity is still lead-only, the action instead prompts to link or create a Client.

**6. Won -> Project hand-off:** "Start Project" navigates into the existing
`ProjectSetup.jsx` flow with `existingClientId` pre-filled from the Opportunity's
`client_id`, and passes the Opportunity's id through so the created `Project` can record
where it came from. Adds `Project.opportunity_id` (FK, nullable) -- set on creation when
reached via this hand-off, left null for every other project-creation path. Once set,
`Opportunity.project_id` is written back too. This is the concrete hook build index step
8 (Quotations) needs to "link back to the Opportunity that produced it."

**7. Dashboard wiring** (`backend/app/api/dashboard.py`, `frontend/src/Dashboard.jsx`):
- "Open opportunities" tile: real count of Opportunities with `stage` not in
  (`WON`, `LOST`), replacing its `ComingSoonTile`.
- "Sales pipeline" panel: real by-stage counts (`NEW`/`CONTACTED`/`QUALIFIED`), replacing
  its `ComingSoonPanel`. **No monetary value shown** -- an Opportunity has no
  estimate/quotation figure yet at this stage, and fabricating one would violate this
  register's own data-honesty principle (Amendments 41/42's precedent); value only
  becomes real once a Cost Sheet/Estimate exists post-conversion.
- Sidebar/tab-strip "Opportunities" nav item drops its `muted`/"Soon" badge.

**8. Follow-ups screen/count extended to include Opportunities** (touches Amendment 43's
already-shipped `FollowUps.jsx`/`dashboard.py`): `followups_due_count` and the Follow-ups
screen's list both fold in Opportunities with a due/overdue `next_follow_up_date`
alongside Clients', sorted together. This is what actually closes Section B.2's "my open
items" gap, which Amendment 43's own registration explicitly flagged as blocked on this
step's `created_by_id`/owner field.

**9. "My follow-ups" per-rep filter** on the (now-combined) Follow-ups screen -- a toggle
that filters to records where `created_by_id` (Opportunity) matches the logged-in user.
`Client` still has no owner field, so this toggle only ever narrows the Opportunity half
of the list; Clients remain org-wide-only in the filtered view too, with a short note
explaining why, rather than silently dropping them.

### Explicitly out of scope
- Any change to `Client` itself beyond `link-client` reading/writing `client_id` on
  `Opportunity` -- `Client.type`/GSTIN/etc. are untouched.
- Monetary/pipeline value tracking on Opportunities (see item 7).
- Notifications/alerts on overdue follow-ups (same boundary Amendment 43 already drew).
- Converting `PATCH .../link-client` into a one-click "promote lead to full Client"
  auto-fill flow -- linking only ever attaches an already-existing `Client` id; creating
  one still goes through the existing, unchanged "Add a client" form.

### Acceptance criteria
- Cannot create an Opportunity without `next_follow_up_date`; cannot move its stage to
  `NEW`/`CONTACTED`/`QUALIFIED` without supplying a fresh one; moving to `WON`/`LOST`
  clears it.
- Add Enquiry creates a lead-only Opportunity (no `Client` row) that shows correctly in
  the Opportunities screen's "Leads" filter.
- Linking an existing Client moves that Opportunity into the "Clients" filter.
- Follow-ups screen and Dashboard's `followups_due_count` both include Opportunity rows
  alongside Client rows, correctly sorted, with the same overdue-red convention.
- "Open opportunities" tile and "Sales pipeline" panel show real counts, no fabricated
  values.
- "Start Project" from a Won, Client-linked Opportunity lands in New Project Setup with
  the client pre-selected; the created Project's `opportunity_id` is set and readable back
  from the Opportunity.
- No existing Client/Dashboard/Follow-ups test regresses; full new test coverage for the
  Opportunity model's stage-transition and mandatory-date rules.

### Open decisions (proposed defaults)
1. **Pipeline stages**: proposed `NEW → CONTACTED → QUALIFIED → WON/LOST` (5 stages,
   matching `QuotationStatus`'s own simplicity) -- not a richer, more granular pipeline.
2. **Extending Amendment 43's Follow-ups screen/count to include Opportunities (item 8)**
   rather than shipping a second, separate follow-ups view: proposed yes, since a
   telecaller working both Leads and Clients needs one queue, not two.
3. **"My follow-ups" per-rep toggle (item 9)** ships in this same Amendment rather than
   waiting for a later one: proposed yes -- it's what Amendment 43's registration named
   as the concrete reason this data (`created_by_id`) was worth building now.
4. **Implementation phasing**: proposed shell-first, same precedent as Amendment 36 --
   landed as an ordered sequence of PRs under this one Amendment number (model + API +
   mandatory-date rules first, then Add Enquiry + the Opportunities screen, then the
   Won-Project hand-off, then Dashboard/Follow-ups wiring last) rather than one PR.

### Approval
☑ Approved as proposed, all decisions
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 23 September 2026
