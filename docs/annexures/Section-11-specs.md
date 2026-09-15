# Section 11 — Draft Specification for Director Approval

**Date: 15 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

---

## Amendment No. 12 — Dashboard Drill-Down & Navigation Restructure

**Registered scope (Annexure 2, §2):** confirmed by reading the actual code (not
assumed): `Dashboard.jsx`'s five summary tiles (Open Projects, Pending Estimates,
Pending Quotations, Overdue Clients, Won This Month) are plain numbers with no click
handler at all — there is no screen anywhere in the app that lists the full set behind
any of them, only a five-row "Recent projects" list. Separately, the Director's top nav
carries 10 flat items today (Dashboard, Pricing Calculator, Rate Sheet, Help, Clients,
Reports, Price Requests, Vendors, Master Settings, Sports & Scope Admin, Cross-Sell
Add-ons, Audit Log, All Quotations), more than are used day to day.

Director supplied a target nav structure (image, 15 September): eight top-level groups
— **Dashboard, Quotation, Projects, Client, Vendor, Tools, Reports, Admin** — each with
its own sub-items, plus a ninth placeholder group, **Education**, whose contents will be
specified separately once the rest of this section ships. Also requested: the frontend
should read as more dynamic/animated, within the existing dark/gold theme (Amendment
1) — not a redesign.

### Part A — Map the target structure to what exists vs. what's new

Checked every item in the supplied structure against the actual codebase:

| Group | Item | Status |
|---|---|---|
| **Dashboard** | Total Summary | Exists — tiles become clickable (Part B) |
| **Quotation** | Pending Quotation | New: filtered view over the existing All Quotations screen (statuses draft/released/sent) |
| | Old Quotation | New: same screen, filtered to won/lost/expired/superseded |
| | New Quotation | No standalone action exists or should — a Quotation always requires a verified Cost Sheet and an approved Estimate option first (M.2 rules 1–2). Maps to **+ New Project**, the real entry point into that pipeline. |
| **Projects** | Create Cost Sheet of Quotations | Same real entry point as "New Quotation" above — **+ New Project** |
| | Quotation-winning projects | New: a "Won Projects" list (projects with ≥1 Won quotation) |
| | Procurement statement | Exists, per-project, just buried — the **Consumption Sheet (J.3)** already shown on each project's own Documents screen (material, spec, unit, quantity, rate, source, derived straight from that project's Cost Sheet). Director confirmed this is exactly what "which material and how much required in this project" means. Nav fix, not new capability — see Decision A below. |
| **Client** | Create New Client | **Gap found**: today a client can only be created *inline* while setting up a new project — there is no standalone "add a client" action. New: a real Add Client form on the Clients screen. |
| | List of Clients | Exists (`ClientsAdmin.jsx`) |
| **Vendor** | Create New Vendor | Exists (`VendorsAdmin.jsx`) |
| | List of Vendors | Exists (same screen) |
| **Tools** | Price calculator | Exists (Pricing Calculator) |
| | Rate sheet | Exists |
| | One simple calculator | **Unclear what this is** — see Decision B below |
| | Price Requests | Exists |
| **Reports** | All Types of Reports | Exists (Pipeline / Margin / Override Summary already in one screen) |
| **Admin** | Sports & Scope | Exists |
| | Master Settings | Exists |
| | All other admin headers or sections | Cross-Sell Add-ons, Audit Log, All Quotations (the Director-only admin one) fold under this group instead of sitting at top level |
| **Education** | — | Placeholder only this wave — a real nav slot, empty screen with "Coming soon," content specified in a future section |

### Part B — Dashboard tiles become real drill-downs

- **Open Projects** tile → a new "All Projects" screen: every project, searchable by
  project number/client name, filterable by status (open / won / lost), same pattern as
  the existing All Quotations screen (Section 9).
- **Pending Estimates** tile → a new "All Estimates" screen, same pattern, filtered to
  estimates with at least one option still pending client approval.
- **Pending Quotations** / **Won This Month** tiles → both covered by All Quotations
  with the right filter pre-applied (statuses draft/released/sent for "pending";
  released_at within the current month + status=won for "won this month").
- **Overdue Clients** tile → links straight to the Clients screen (it already surfaces
  the Overdue flag per client; no new screen needed).
- **Recent Activity** section is removed from the Dashboard entirely (Director
  instruction) — the Audit Log screen remains the full, raw record.

### Part C — More motion, same theme

Checked what's actually animated today: only Sport Selection's tiles have real motion
(`hover:-translate-y-0.5`, `transition-all duration-250`, from Amendment 1's own
"animated sport-tile selection" acceptance criterion). Everything else — the nav bar,
Dashboard tiles, project/quotation lists, most buttons — only has a flat
`transition-colors`, no movement. Proposed: extend the same restrained motion language
(subtle lift/scale on hover, 200–300ms, matching Amendment 1's own "0.2–0.3s" spec) to
Dashboard tiles, list rows, and nav items — no new colors, no new typefaces, same gold
accent on the same dark surface.

### Decision A — resolved (15 September 2026)

**Procurement statement = the existing Consumption Sheet (J.3), reachable per-project
from the Projects nav group.** Director confirmed this means "which material and how
much is required in a particular project, connected to its Cost Sheet" — exactly the
Consumption Sheet already computes. No new backend capability needed; "Projects →
Procurement statement" opens the project picker (same list the All Projects drill-down
uses), then that project's existing Consumption Sheet view.

### Decision B — resolved (15 September 2026)

**A basic +/−/×/÷/% calculator widget**, unrelated to the Pricing Calculator — for quick
arithmetic while working in the app (e.g. adding up a few figures) without switching to
the phone/OS calculator. Pure client-side, no backend involved, no persistence needed.
Lives under Tools alongside Price Calculator / Rate Sheet / Price Requests.

**Acceptance criteria:** Director's nav shows 8 top-level groups (9 once Education has
real content) instead of 10 flat items; every Dashboard summary tile opens a real,
filtered list instead of doing nothing; Clients screen gains a working "+ Add Client"
action; hover/transition motion is visibly present on at least Dashboard tiles, list
rows, and nav items, using the existing gold-on-dark palette only.

---

## Approval

Amendment 12 overall: ☑ Approved ☐ Changes ☐ Later -- "Approved, go ahead and build it" (15 September 2026)
Decision A (Procurement statement): ☑ Resolved -- existing Consumption Sheet, nav fix only
Decision B ("one simple calculator"): ☑ Resolved -- basic +/-/x/÷/% widget under Tools,
client-side only

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 15 September 2026
