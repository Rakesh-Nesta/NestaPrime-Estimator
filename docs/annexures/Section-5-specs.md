# Section 5 — Draft Specifications for Director Approval

**Date: 13 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Annexure 2's own priority sequencing pairs "No. 10 full handbook + No. 6a/6c
(rights + reports)" as Section 5 — "team trained; control and oversight." Section 4's
Quick Start card (No. 10, item 1 of 4) is already live; this spec covers the remaining
three items (No. 10's items 2-4, No. 6a, No. 6c).

---

## Amendment No. 10 — Full Handbook (items 2-4 of 4)

**Registered scope (Annexure 2, §2):** "Full handbook: every screen explained in plain
business language with screenshots -- what each field means, what to fill when the
client hasn't provided data, and worked examples from real projects (e.g. the Ujjain
Pickleball job). Separate short sections per role: Estimator guide and Director/Admin
guide (users, rates, reports). FAQ: the twenty questions the team will actually ask."

### Current state
`frontend/src/Help.jsx` is the Quick Start card only (Section 4) -- a single screen, 5
steps, print-friendly. Its own top comment already flags items 2-4 as "Section 5, not
built here." No per-role content branching exists yet; `Help` takes no `role` prop.

**Discrepancy worth flagging:** the registered text names "the Ujjain Pickleball job" as
a worked example. No pickleball job exists in the 23 historical quotations reviewed for
Note R1 -- the actual Ujjain job on record is a squash court (RK Bansal School, Dec
2022). Proposing to use that real job as the worked example instead, unless a pickleball
project exists in the app's own project records that I haven't seen.

### Proposed spec
Extend `Help.jsx` into a tabbed screen: **Quick Start** (unchanged) | **Full Handbook** |
**Estimator Guide** | **Director/Admin Guide** | **FAQ**.

- **Full Handbook**: one entry per real screen in the app's own screen graph (Setup,
  Sport Selection, Scope, Site Survey, Cost Sheet Builder, Rate Sheet, Estimate, Quotation,
  Reports, Clients, Master Settings, User Management, Audit Log) -- each with: what it
  does, a field-by-field explanation in plain language, what to do when the client hasn't
  provided a value (matches Amendment 2's blind-quoting T&C language where relevant), and
  one worked example per section drawn from a real project on record (the Ujjain squash
  job above; others to be picked from real projects as each section is written).
- **Estimator Guide** (Sales + PM, since they're the two daily hands-on-keyboard roles):
  the full daily workflow start to finish, cross-referencing the Quick Start card's 5
  steps but going deeper on each.
- **Director/Admin Guide**: User Management, Rate Sheet confirmation workflow (Manual →
  AI), Reports (once 6c below exists), Master Settings, Audit Log -- the screens Sales/PM
  don't see at all per Amendment 4's role-based nav hiding.
- **FAQ**: twenty real questions, drawn from this session's own findings rather than
  invented -- e.g. "I forgot my password," "Rate Sheet is empty for the rate I need, what
  do I do," "a Quotation option was rejected, now what," "how do I revise a Sent
  Estimate," "why can't I deactivate this Director account," "what does 'below floor'
  mean," "why did my dimensions show as NonexNone" (historical, now fixed), plus general
  ones (creating a user, resetting someone else's password, printing a Quotation PDF).

**Format**: same print-friendly pattern as Quick Start (`window.print()`, `@media print`
hides chrome); each of the five tabs printable independently. Version-numbered per the
registered "Maintenance" note -- this ships as v2 of the handbook (v1 was the Quick Start
card alone).

**Acceptance criteria:** a new Sales/PM hire can answer at least 15 of the 20 FAQ
questions without asking the Director; the Full Handbook covers every screen currently
reachable from the nav; Director/Admin Guide content doesn't appear for Sales/PM roles;
each tab prints cleanly to its own page(s).

---

## Amendment No. 6a — Role-Based Permissions

**Registered scope (Annexure 2, §2):** "Role-based permissions (what each role can see/do)."

### Current state
Enforcement is entirely hardcoded: `require_roles(*allowed_roles)` (`backend/app/core/
auth.py`) is called individually at 192 call sites across 41 backend files -- there is no
permissions table, matrix, or admin screen. Amendment 4 already pulled forward "the
minimum viable slice" (Admin nav items hidden entirely for non-Admin/Director roles) as a
display-only mirror of the server-side checks, not a new permissions engine.

### Open decision -- needs Director input before implementation
Turning every one of those 192 hardcoded checks into a live, Director-editable
permissions table is a large rearchitecture with real risk (an editable toggle for e.g.
K.3's "Sales never sees cost" rule would be a governance change, not a UI feature). Two
honest options for this wave:

**Option A -- Read-only Role & Permissions viewer (smaller, safer).** A new screen under
Master Settings that documents, per role, what that role can currently see/do --
generated from the actual `require_roles()` calls (or maintained as a hand-written
reference table kept in sync with them), Director/Admin only. Satisfies "what each role
can see/do" as visibility, not editability. Nothing about actual enforcement changes;
zero risk of accidentally loosening a rule like K.3.

**Option B -- Editable permissions for a defined subset (larger, real 6a).** A new
`role_permissions` table + admin screen letting the Director toggle role access for a
specific, named list of *non-safety-critical* screens/actions (e.g. who can see Pricing
Calculator, who can see Reports, who can create Price Requests) -- while explicitly
leaving the safety-critical rules named elsewhere in the blueprint (K.3 cost visibility,
M.2 Director-only Quotation release, the Director-count guardrails on User Management)
as hardcoded and NOT toggleable, since those are deliberate business rules rather than
preferences.

This spec proposes **Option A** for Section 5 (smaller, ships faster, zero governance
risk) with Option B flagged as a possible later wave if the Director wants genuine
editability -- but this is exactly the kind of scope call that should go to the Director
rather than be decided in code. Marked open in the Approval section below.

**Acceptance criteria (Option A):** Master Settings gains a "Role & Permissions" tab
(Director/Admin only) listing every role and, per role, the screens/actions it can
access, matching what `require_roles()` actually enforces at the time of viewing.

---

## Amendment No. 6c — Reports (daily/weekly/monthly/full-year/custom ranges)

**Registered scope (Annexure 2, §2):** "Reports for daily / weekly / monthly / full-year
/ custom ranges."

### Current state
`backend/app/api/reports.py` + `frontend/src/Reports.jsx` already implement a working
Draft/Released report workflow with three types (`pipeline`, `margin`,
`override_summary`), role-gated visibility, and hash-verified content -- generated over
an arbitrary `period_from`/`period_to` custom range. **Custom ranges already work.** What
the register asks for beyond that is the daily/weekly/monthly/full-year *framing* --
today, a user must pick exact calendar dates by hand every time.

### Proposed spec
Add period **presets** to the existing report-generation form -- Today, This Week, This
Month, This Year, Custom -- that compute and fill `period_from`/`period_to`
automatically against the server's current date; Custom keeps today's manual
date-pickers. Purely additive to the existing `POST /reports/generate` endpoint (no new
fields needed, since `period_from`/`period_to` already exist) -- the three current report
types (pipeline, margin, override_summary) all become selectable at any of the five
periods.

**Acceptance criteria:** selecting "This Month" and Report Type "Pipeline" generates a
report scoped to the current calendar month's start/end with no manual date entry;
"Custom" still behaves exactly as it does today; existing Draft/Release workflow and
role gating are unchanged.

---

## Approval

Amendment 10 (full handbook): ☐ Approved ☐ Changes ☐ Later
Amendment 6a (Option A -- read-only viewer): ☐ Approved ☐ Changes ☐ Later
Amendment 6a (Option B -- editable subset, alternative to A): ☐ Approved instead ☐ Not now
Amendment 6c (period presets): ☐ Approved ☐ Changes ☐ Later

Open items needing a Director answer before/alongside implementation:
1. Ujjain Pickleball vs. Ujjain Squash as the Amendment 10 worked example (or a different
   real project if one exists in the app's own records that this review missed).
2. 6a: Option A vs Option B (see above).

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 13 September 2026
