# Sales Experience & Dashboard Plan (Draft)

**Status: DRAFT — not an Annexure 2 Amendment.** Nothing in this document is
approved. Per the Director's explicit instruction, everything below is being
decided on paper first; no code changes will be made against any item here
until it is individually approved and then run through the normal Annexure 2
loop (Record → Director approves → spec doc → branch/PR/tests/merge →
deploy).

**Governing goal, in the Director's own words (2026-09-22):** "my purpose to
not create app the actual purpose people love to use this app with easy and
fulfill the actual reequipment. so my hole point round to sales persons or
his actual bottle neck." Every item below is being evaluated against that —
does it remove a real, observed obstacle for a Sales rep's daily work — not
against process purity or completeness for its own sake.

**Explicitly NOT on the table:** the underlying document sequence Cost Sheet
→ Estimate → Quotation → (Won) → Work Order/Procurement stays as-is. An
earlier proposal to reorder Quotation before Cost was walked back once the
margin-based pricing math (cost must exist before a sell price can be
computed) was explained — that is not being revisited here.

---

## Section A — Sales-rep UX fixes (from screenshots, 2026-09-22)

Five concrete complaints, each independently verified against the live
codebase before being listed here.

### A.1 Existing-client city not auto-filled
**Current state:** `ProjectSetup.jsx` hardcodes `city: "Mumbai"` in
`emptyForm` (line ~56-79) and only auto-fills package/payment-terms (lines
126-148) when an existing client is selected — never city. Root cause is
structural: `Client` (`backend/app/models/client.py:25-74`) has no
structured `city` column at all, only free-text `billing_address`.
**Fix shape:** add a structured `city` field to `Client`, backfill from
existing `billing_address` where extractable, auto-fill `ProjectSetup`'s
city field from it on existing-client selection.
**Scope:** backend model + migration + frontend auto-fill. Small-medium.

### A.2 Create-Cost-Sheet form stays visible after a sheet exists
**Current state:** `Documents.jsx:451-476` — the create-cost-sheet input is
never disabled once a sheet exists; the button is only
`disabled={!!active}`. Confusing for Sales, who can't create one anyway
(`COST_ROLES = ("pm","director")`) but still sees an always-live form.
**Fix shape:** hide/collapse the create form once an active cost sheet
exists, same pattern the existing-sheet action row (`Documents.jsx:400-408`)
already uses.
**Scope:** frontend only. Small.

### A.3 Scope Checklist needs a bulk "not applicable"
**Current state:** `ScopeChecklist.jsx:91-107` — 30 checkboxes, each toggled
individually (`handleToggle`, lines 32-46), no bulk control. The Director
raised this same point earlier in the project and it was not acted on then.
**Fix shape:** a "mark all remaining as not applicable" action.
**Scope:** frontend only. Small.

### A.4 Site Survey has no forward navigation — genuine dead end
**Most severe of the five.** **Current state:** `SiteSurvey.jsx:190-194`
has only a "← Back" control; `App.jsx:488-495` mounts `<SiteSurvey
onBack={...} />` without ever passing an `onNext` prop, unlike
`ScopeChecklist` which receives `onNext`/`onDocuments`/`onSiteSurvey`
(`App.jsx:478-487`). A Sales rep who finishes a Site Survey has no button
to press — they are stuck. (Separately confirmed: fields are NOT all
mandatory — only `photo_count >= 4` gates "Mark Completed",
`backend/app/api/site_surveys.py:24`. That part of the complaint was a
misread of the UI, not a real requirement.)
**Fix shape:** wire a real forward path out of Site Survey once completed.
**Scope:** frontend only, but this is the one item on this list that is a
genuine functional blocker, not a convenience gap. Recommend prioritizing
it above A.1–A.3.

### A.5 No "what's next" guidance for the Sales role
**Current state:** stage headers throughout `Documents.jsx` (lines ~384,
600, 1068, 1434) label the current stage but never say what happens after
Sales finishes their part, or whose court the ball is in.
**Fix shape:** a small persistent status line — "Cost Sheet with PM,
awaiting pricing" / "Quotation sent, awaiting client response" — visible to
Sales at each stage.
**Scope:** frontend only, touches several screens. Medium.

---

## Section B — New Sales-rep capabilities (not UX fixes, missing features)

Verified against the live backend on 2026-09-22 — none of the three exist
today in any form.

### B.1 Client follow-up / reminder tracking
**Verified gap:** `Client` model (`backend/app/models/client.py`) has no
due-date, next-action, or reminder field. No reminder mechanism exists
anywhere in `backend/app/`. A Sales rep has nothing in the app prompting
"call this client back Thursday" — tracked outside the app today, if at
all.
**Recommended shape:** a `next_follow_up_date` (+ optional short note) on
Client, with a "due for follow-up" indicator surfaced on the Sales rep's own
dashboard view (see Section D).
**Assessment:** highest-leverage single addition on this list for daily
Sales use — this is a bottleneck a Dashboard redesign alone won't fix.

### B.2 No Sales-scoped "my open items" view
**Verified gap:** the existing Dashboard tiles (`Dashboard.jsx:46-57`) are
org-wide counts (open projects, pending estimates, pending quotations,
overdue clients, won this month) — not "what's mine and waiting on me."
This is the concrete backend of complaint A.5.
**Recommended shape:** a Sales-specific panel — their own quotations
awaiting client reply, their own incomplete Site Surveys, their own
follow-ups due — distinct from the Director's org-wide view.

### B.3 No global quick search
**Verified gap:** search inputs exist only inside `AllProjects.jsx:70`,
`AllEstimates.jsx:64`, `AllQuotations.jsx:161` (`placeholder="Search
project or client…"` in each) — there is no header-level search. Worse,
`AllQuotations` is gated Director-only in the nav (`App.jsx:137-142`), so
Sales cannot reach even that one. A rep on a call with a client has no fast
way to pull up that client's record.
**Recommended shape:** a lightweight global search reachable from the
header, scoped to client/project (not quotation financials), available to
Sales.

**Already solid — not a gap, noted so it isn't rebuilt:** WhatsApp/
Telegram/email sending to a client is fully wired end-to-end (`Message`
model, `backend/app/services/wa_gateway.py`, `MessagesPanel.jsx` already
mounted on the Quotation row in `Documents.jsx:1273`) and Sales already has
access (`DOCUMENT_ROLES = ("sales","pm","director")` in
`backend/app/api/messages.py:35`).

---

## Section C — Quotation descriptiveness (from the reference PDF comparison)

Triggered by the Director sharing a real historical quotation PDF
(`SEP-85 Quotation for 54 Er Rg Badminton 14.72L.pdf`) and asking that the
app's quotation output become more descriptive/customized. Confirmed
constraint: **pricing must stay lump-sum** — the client never sees a
priced, itemized breakdown — but descriptive product/scope detail (what
standard vs. premium materials are being used) should show without a price
attached to each line.

Three pieces, in the order the Director selected them (all three, via
`AskUserQuestion`):

1. **Richer AI-generated cover letter** — extends the existing Amendment 13
   cover-note feature (`POST /quotations/{id}/draft-cover-note`,
   `backend/app/api/documents.py:~2399-2455`), which today generates a
   generic 2-3 sentence note from client/city/sport/package/total only.
   Needs a materially richer prompt and a printed addressee/signatory
   block matching the reference PDF's structure.
2. **Descriptive scope-of-work section, no per-line pricing** — sourced
   from the Cost Sheet's own line data (materials/specs), rendered as
   descriptive text/specification list in the PDF
   (`backend/app/api/pdf_documents.py:~741-746` is where cover-note
   content is currently gated into the render), with the total staying a
   single lump-sum figure exactly as today.
3. **Director-configurable Terms & Conditions / Bank Details / Notes** —
   the reference PDF has a 13-clause T&C and a Special Note/Bank Details
   block; today's quotation PDF has no configurable equivalent.

**Scope:** backend (AI prompt work, new PDF sections) + frontend (any new
Director-facing config screen for T&C/bank details). Medium-large.

---

## Section D0 — Header definitions: what each one means and carries

Requested 2026-09-22: before any redesign, define what every header/nav item
actually means and is for, since some are already confusable (the Director's
own example: Quotation vs. Estimate). Verified against the live code, not
guessed.

### The Quotation vs. Estimate distinction (the example given)

| | **Estimate** | **Quotation** |
|---|---|---|
| What it is | Exploratory, multi-option proposal — Budget/Standard/Premium per sport, each a **price range** (`price_low`-`price_high`, +/-5% around target margin) | The single, firm, **frozen** offer — one final price |
| Purpose | Let the client react before committing (approve / reject / demand an option) | The binding document once the client has actually chosen something |
| Can be created when | Its Cost Sheet is Verified | The Estimate shows at least one client-approved/demanded option |
| Covers | Every sport/package still in play | Only the approved subset the client said yes to |
| Plain framing | **The menu** | **The bill** |

**Structural finding:** these two are not symmetric in the nav today. Quotation
has its own dropdown (New / Pending / Old). **Estimate has no nav group at
all** — reachable only via the Dashboard's "Pending estimates" tile or by
opening a project's Documents screen. That asymmetry is very likely the root
of the Director's own confusion between the two — the app's nav treats one as
first-class and the other as a byproduct, when both are real, sequential
stages (M.1: Cost Sheet -> Estimate -> Quotation).

### Every header, defined

**Dashboard** (standalone link) — post-login landing screen. Org-wide summary
(open projects, pending estimates, pending quotations, overdue clients, won
this month) + recent-projects list. Not a document type itself — a routing/
summary screen (Amendment 4/12: "the app itself is the training," link every
section back to Dashboard). Open to everyone.

**Quotation** (dropdown) —
- *New Quotation* -> actually starts a new **project**, not a Quotation
  document. Same underlying action as Projects -> "Create Cost Sheet of
  Quotations" below — two differently-labeled menu paths triggering the
  identical function (`handleNewProject()`). Open to everyone.
- *Pending / Old* -> drills into the Quotation list filtered by status.
  **Director-only** — quotations carry cost/margin figures (K.3).

**Projects** (dropdown) —
- *Create Cost Sheet of Quotations* -> also just starts a new project
  (identical to "New Quotation" above). The label is misleading twice over:
  it doesn't create a Cost Sheet (Sales can't; `COST_ROLES` = pm/director
  only) and it doesn't create a Quotation either.
- *Quotation-winning Projects* -> drills into projects with status = won.
- *Procurement Statement* -> a project picker into the existing per-project
  Consumption Sheet (a nav shortcut, not a new capability).
- *All Projects* -> full project list/admin.
- Meaning of "Project" itself: the core engagement container, one per client
  job, holding the Cost Sheet -> Estimate -> Quotation -> Work Order chain
  plus Site Survey and Scope Checklist. Open to everyone.

**Client** (dropdown) — *Create New* / *List*, both land on the same
Clients admin screen. Meaning: the customer/organization master record,
reused across all of that client's projects. Currently a flat record with no
separate pre-project "lead" concept (see the CRM discussion elsewhere in this
doc). Open to everyone.

**Vendor** (dropdown) — *Create New* / *List*. Meaning: supplier master data
for materials/services procurement — unrelated to client-facing sales.
**PM/Director/Procurement only**, correctly hidden from Sales.

**Tools** (dropdown) —
- *Price Calculator* -> a margin/selling-price what-if tool: cost + client
  type -> selling price, using the K.3-protected margin-policy table.
  **Hidden from Sales** (would expose margin logic).
- *Rate Sheet* -> where PM/Director/Procurement/Site Engineer confirm and
  manage the master `RateItem` rates (J.1: nothing drives a real quotation
  until a rate is confirmed here). **Hidden from Sales.**
- *One Simple Calculator* -> a plain +-x/% arithmetic widget, purely
  client-side, unrelated to pricing (`SimpleCalculator.jsx`'s own comment:
  "unrelated to the Pricing Calculator"). **Open to everyone, including
  Sales** — the one Tools item that is.
- *Price Requests* -> the vendor RFQ workflow (send/track price requests to
  vendors, apply GST-basis-converted replies, Amendment 27). **Hidden from
  Sales** (vendor/cost-adjacent).

**Reports** (dropdown, single item: *All Types of Reports*) — the header
itself is open to everyone, but the report **types** inside are individually
gated (`backend/app/api/reports.py:35-37`), and the nav gives no hint of
this:
- *Pipeline* (sourced from Estimates/Quotations) -> sales, pm, director.
- *Margin* (sourced from Cost Sheets/Quotations/Overrides) -> pm, director
  only.
- *Override Summary* -> director only.
So a Sales rep who opens Reports will only actually be able to generate a
Pipeline report — worth signalling that inside the screen rather than
finding out by trial.

**Admin** (dropdown) —
- *Sports & Scope* -> manage Sport/ScopeItem master data. Hidden from Sales.
- *Master Settings* -> the global `Setting` table (K.1 pricing constants +
  Director overrides). Hidden from Sales.
- *Cross-Sell Add-ons* -> the CrossSellAddon catalog. **Director only.**
- *Audit Log* -> full system audit trail. **Director only.**
- *All Quotations* -> the unfiltered Quotation list. **Director only.**
- *Help* -> handbook/help content. **Open to everyone** — the one
  non-restricted item sitting inside a menu labelled "Admin," where a Sales
  rep has no reason to think to look. Candidate to move out of Admin
  entirely (own header, or fold into Education).

**Education** (standalone link, not a dropdown) — training/handbook content
(Amendment 4/10: "the app itself is the training"). Open to everyone.

### Mismatches surfaced by this pass (candidates for fixing, not yet approved)

1. "New Quotation" and "Create Cost Sheet of Quotations" are the same action
   under two different, both-somewhat-wrong labels — pick one true label
   (e.g. "New Project") and remove the duplicate entry point.
2. Estimate has no header of its own despite being a real, named pipeline
   stage — give it one, or fold a clearly-labelled Estimates entry into the
   Quotation dropdown so the two stages read as siblings, not as one
   first-class thing and one afterthought.
3. "Help" lives inside "Admin," the one menu everyone else in it is locked
   out of — move it out where a Sales rep would actually look for it.
4. Reports doesn't signal that Sales only gets the Pipeline report type —
   worth a small in-screen note rather than a silent narrower result.

---

## Section D — Dashboard redesign + nav-shell decision

**Status: reference gathering in progress.** The Director has shared one
reference screenshot and said "I like this and this is my expectation," and
is preparing a second option to compare before deciding.

**Current state:** `Dashboard.jsx` is 5 static tiles (label + number, hover
lift only, no charts) plus a flat text list of recent projects — confirmed
by direct read on 2026-09-22.

**What the first reference adds:** trend context per tile (e.g. "2 new this
month"), a revenue bar chart, a pipeline-stage breakdown, a
tabbed/searchable project table with per-row progress bars and status
pills, a "needs your attention" action panel, and a live activity feed —
plus a **left sidebar nav**, replacing the current top-nav-with-dropdowns
structure documented in full in this project's nav audit
(`App.jsx:129-213`: Dashboard / Quotation / Projects / Client / Vendor /
Tools / Reports / Admin / Education).

**Open decision, not yet made:** top nav (current) vs. sidebar nav (as in
the reference) — this is an app-wide shell change, not a dashboard-only
one, and should be decided deliberately rather than inherited from whichever
reference image is chosen.

**Assessment:** this is the largest single item on this plan — new backend
aggregation endpoints (trend %, pipeline-stage counts, activity feed) plus a
genuine frontend redesign. It is Director/management-facing (pipeline
value, win totals) more than it is Sales-facing, so per the governing goal
above it should be sequenced **after** Sections A and B, not before —
unless the Director decides otherwise once the second reference is in hand.

**Second reference option received 2026-09-22** — a "NestaPrime CRM" mockup,
left sidebar (Overview / Leads & Clients / Opportunities / Quotations /
Projects / Payments / Follow-ups / Team & Access). Tiles: Open opportunities
(with total pipeline value), Follow-ups due (today & overdue), Pending
quotations, Active projects, **Payments overdue** (rupee total). An
"Orders & collections" chart (won value vs. cash received, distinct lines),
a sales-pipeline donut by stage (Discovery/Estimation/Quotation/
Negotiation), an Active Projects table with stage/next-milestone/progress,
and a "Your next moves" panel — named owner + due date per action item
(e.g. "Confirm revised scope — Overdue, 21 Sept, Rakesh").

**Assessment vs. the first reference:** structurally different, not just a
reskin. The first reference is a prettier version of the existing
Project-centric dashboard (more counts, a chart, a table). This second one
is a direct visualization of the **CRM-lite direction already discussed
under Section B and the Opportunity/pipeline idea** (see
`PROJECT-BLUEPRINT.md` Section 7) — Follow-ups due and "Your next moves"
are exactly the follow-up/reminder gap verified missing in Section B.1;
Payments overdue is exactly the forward-looking due-date gap verified
missing against `WorkOrderPaymentEntry`; the pipeline donut is the
Opportunity-stage tracking verified missing entirely. Choosing this option
is not a styling choice — it commits to building the `Opportunity` entity,
pipeline stages, and payments-due extension, which is real backend
modeling, not a UI pass. Both references independently point to a sidebar
nav, so if either is chosen the nav-shell decision (open item above) is
effectively answered: sidebar.

**Recommendation:** if the goal is genuinely "what makes Sales/Director
love using this daily" rather than "what looks best," this second option is
the stronger pick — it surfaces the real gaps (follow-ups, payments due,
opportunity pipeline) that are otherwise invisible today, not just prettier
counts of what's already shown. The cost is real: it requires the CRM-lite
backend work (Section 6/7 of `PROJECT-BLUEPRINT.md`) to have real data
behind it, not sample data.

**Recommendation (nav-shell + build order):** build the nav-shell decision
and the dashboard redesign together in one pass (not dashboard-then-nav-
later, which would mean rebuilding the dashboard shell twice), broken into
normal reviewable PRs like every other amendment on this project — not one
giant unreviewable change.

---

## Section E — Header-by-header build index (new CRM-shaped concept)

Requested 2026-09-22, once the second reference (CRM sidebar) was chosen as
the direction: an index plan to build **one header at a time**, in order.

### E.1 — First: where does EVERY current header land? (open decision)

Both reference mockups are simplified demos — neither shows every screen
this app actually has in production today. Before sequencing a build, every
existing header needs a home in the new structure, not just the ones the
mockup happens to show, or real functionality gets orphaned mid-migration.

| Today | New sidebar (from the CRM reference) | Status |
|---|---|---|
| Dashboard | **Overview** | Rebuilt last (see E.2) — rolls up every other header's data |
| Client | **Leads & Clients** | Direct rename/re-home, extended with the follow-up-date field (Section B.1) |
| *(none today)* | **Opportunities** | Net-new — the `Opportunity` entity + pipeline stages from Section 6/7 |
| Quotation | **Quotations** | Direct re-home, same underlying documents |
| Projects | **Projects** | Direct re-home; Section A's UX fixes (A.1-A.5) folded in here |
| *(none today — `WorkOrderPaymentEntry` is close but not surfaced)* | **Payments** | Extends the existing model with forward-looking due-dates |
| *(none today)* | **Follow-ups** | Net-new, small — surfaces the Section B.1 follow-up-date field as its own view |
| User Management + Role Permissions Viewer | **Team & Access** | Direct re-home |
| **Vendor** | *not shown in either reference* | **Needs a decision** — its own header still, or folded under Team & Access / Projects? |
| **Tools** (Price Calculator, Rate Sheet, Simple Calculator, Price Requests) | *not shown* | **Needs a decision** |
| **Reports** | *not shown* (only an "Export report" button appears on Overview) | **Needs a decision** — a full header, or does "Export report" cover it? |
| **Admin** (Sports & Scope, Master Settings, Cross-Sell Add-ons, Audit Log, All Quotations) | *not shown* | **Needs a decision** — likely folds into Team & Access as the Director-only area, but not yet confirmed |
| **Education / Help** | *not shown* | **Needs a decision** |

**This mapping needs Director sign-off before Phase 1 below starts** —
otherwise Vendor/Tools/Reports/Admin/Education risk being silently dropped
partway through the rebuild simply because neither reference pictured them.

### E.2 — Build order, one header at a time

Sequenced so nothing is built on top of data that doesn't exist yet, and so
the cheapest, already-approved, highest-leverage-for-Sales items go first
(matching the Director's own stated priority — see the top of this
document). **Update, 2026-09-22 (Director decision — shell-first):** Overview
is no longer a separate final step. Its visual shell is built in step 1,
with honest empty states, then wired incrementally as each later step's real
data ships -- see step 1 below.

**Update, 2026-09-22 (Director decision — persona-driven resequencing).**
The Director clarified who "Sales rep" actually means in this app: an
office-based telecaller who works leads by phone and sends clients
quotations/details -- not the field-based role (that's "Engineer," i.e. the
existing `site_engineer` role, who owns Site Survey). Against that persona,
Opportunities/Follow-ups (lead-pipeline tracking, mandatory-follow-up-date
discipline) is the actual highest-leverage work, not the remaining Section A
polish items -- a telecaller with no system tracking "who to call today,
what was promised" is the real daily pain. Leads & Clients / Follow-ups /
Opportunities move ahead of Amendments 37-39 in the order below. Amendment
35 (Site Survey) still shipped first regardless -- it was already
spec-approved and cheap -- but is understood as an Engineer-facing fix, not
the Sales-persona lever.

1. **Nav shell + Dashboard shell (shell-first)** — DONE, Amendment 36,
   deployed 2026-09-22. Sidebar + Overview shell built with honest empty
   states, wired incrementally as each step below ships.
2. **Site Survey Next button** — DONE, Amendment 35, deployed 2026-09-22.
   Engineer-facing, not the Sales-persona lever, but cheap and already
   approved so it shipped first regardless.
3. **Leads & Clients** — DONE, Amendment 42, 2026-09-23. Re-homed Client
   screens (already done via Amendment 36); added `next_follow_up_date` +
   `follow_up_note` to `Client` (Section B.1). Prerequisite for steps 4-5
   below.
4. **Follow-ups** — REGISTERED & SPECCED, Amendment 43, 2026-09-23 (spec:
   `docs/annexures/Section-49-specs.md`, pending Director approval). Surfaces
   due/overdue follow-ups as its own view, org-wide only (no per-rep
   filtering yet -- `Client` has no owner field, so Section B.2's full "my
   open items" goal is not fully closed by this step; that awaits step 5's
   `Opportunity.owner`). Wires Dashboard's "Follow-ups due" tile and "Your
   next moves" panel to real data. Depends directly on step 3's new field.
5. **Opportunities** — Amendment 44, approved 2026-09-23 (spec:
   `docs/annexures/Section-50-specs.md`). Phase A (model + API + mandatory-
   date rules, PR #164) DONE, deployed 2026-09-23. Add Enquiry UI, the
   Opportunities screen, the Won-Project hand-off, and Dashboard/Follow-ups
   wiring are still pending as later phases. The largest single piece: new
   `Opportunity` entity + pipeline-stage enum,
   linked to Leads & Clients, converts into a Project once Won.
   Mandatory-follow-up-date discipline (Director decision, 2026-09-22: a
   Lead/Opportunity can never be left with no future follow-up date,
   enforced not just at creation but whenever its stage changes or an
   existing follow-up date passes) is a core design requirement of this
   entity, not an add-on. Also closes Section B.2's "my open items" gap
   (Amendment 43 deferred it, pending this step's owner field) and extends
   the Follow-ups screen/count to include Opportunities alongside Clients.

   **Design input, 2026-09-23 (Director, against the "Leads" tab of the CRM
   reference)**: confirms `Client` and `Opportunity`/Lead are genuinely
   different things, not one entity with a status flag --
   - **A real "Lead" vs "Client" distinction**, matching the reference's
     All/Leads/Clients tab filter and per-row "Relationship" badge. Today
     `ClientsAdmin.jsx` has one flat list with no such split.
   - **A separate "Add Enquiry" quick-capture entry point**, distinct from
     "Add a client". A real intake often starts with just a name and basic
     contact -- not enough yet to justify a full Client record (type,
     GSTIN, payment terms, etc.). Forcing the full Client form at first
     contact is itself a friction point for the telecaller persona.
   - **Follow-up matters most exactly at this early, not-yet-qualified
     stage** -- "if we have enquiry but not connected or proper talk to
     client, need follow-up." This is the direct, concrete case the
     mandatory-follow-up-date discipline above exists to cover: an
     Opportunity that's been created but never really engaged is the one
     most likely to silently go cold without a forced next-follow-up-date.
6. **What's-next guidance (Amendment 40)** — still valuable for the
   telecaller persona (lets them answer a client call with a real status
   instead of "let me check"); cheap, independent of steps 3-5, slotted in
   here rather than left behind with 37-39.
7. **Remaining Section A polish (Amendments 37-39)** — existing-client city
   auto-fill, Create-Cost-Sheet form visibility, Scope Checklist bulk
   controls. All three already approved; deprioritized below
   Opportunities/Follow-ups per the persona clarification, not cancelled.
8. **Quotations** — re-home the existing Quotation screens; link back to
   the Opportunity that produced it, once step 5 exists.
9. **Payments** — extend `WorkOrderPaymentEntry` with due-dates/reminders;
   surface "payments overdue" as its own header.
10. **Team & Access** — re-home User Management/Role Permissions; place
    Vendor/Tools/Reports/Admin/Education per whatever E.1 decides (deferred
    until this step — those screens stay reachable from their current
    locations in the meantime, not hidden).

Each numbered step above is still its own Annexure 2 Amendment (or small
group of them) — registered, specced, approved, and built individually per
the normal change process, not built as one continuous unreviewable push.

---

## Open decisions requiring Director sign-off

1. Approve/reject/amend each item in Sections A, B, C, D individually.
2. Sequencing: this document recommends A.4 (Site Survey dead end) first as
   the one genuine functional blocker, then the rest of A and B, then C,
   then D last — pending the Director's agreement.
3. Nav shell: top nav (keep current) vs. sidebar (match reference) —
   app-wide decision, needed before any Dashboard work starts.
4. Second dashboard reference option — pending from the Director; Section D
   stays open until it's in hand and compared.

---

*Prepared by: R. Patni (with AI development assistance) | Date: 2026-09-22*
*This document has no Approval section by design — each item graduates to
its own Annexure 2 Amendment entry and spec doc only once the Director
approves it individually, following the same process as Amendments 1-34.*
