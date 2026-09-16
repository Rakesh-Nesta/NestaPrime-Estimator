# Section 13 — Draft Specifications for Director Approval

**Date: 16 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Annexure 2 v1.11 (register reconciliation, PR #70) confirmed Amendment 10's
own Maintenance clause — "every shipped amendment wave updates the relevant chapter" —
has not been followed since the handbook's v2 build (PR #34, 13 September). Amendments
11, 12, and 13 (14–16 September) all shipped real screens and features with no
corresponding handbook update. This is the one gap from that reconciliation pass that is
genuine undone work, not a documentation-only correction. This spec covers bringing
`frontend/src/Help.jsx` / `handbookData.js` current as v3.

---

## Amendment No. 10 — Handbook Update (v3: missing screens, Hindi terms)

**Registered scope (Annexure 2, §2):** "Full handbook: every screen explained in plain
business language... Language & format: Simple English with Hindi terms where the team
uses them (estimators think in 'labour, material, dhanda' — the handbook should speak
that language)... Maintenance: Handbook version-numbered; every shipped amendment wave
updates the relevant chapter."

### Current state

`handbookData.js`'s `FULL_HANDBOOK` covers 12 screens (Project Setup, Sport Selection,
Scope, Site Survey, Rate Sheet, Cost Sheet Builder, Documents, Pricing Calculator,
Reports, Clients, Master Settings, Audit Log) — accurate for what existed at PR #34.
Seven real, nav-reachable screens shipped since then have no entry at all:

- **All Projects**, **All Estimates**, **All Quotations** (Amendment 12 drill-down /
  Amendment 6b director oversight — `AllProjects.jsx`, `AllEstimates.jsx`,
  `AllQuotations.jsx`, all top-level nav items in `App.jsx`)
- **Vendors Admin**, **Price Requests** (Amendment 7 — `VendorsAdmin.jsx`,
  `PriceRequests.jsx`, top-level nav items)
- **Cross-Sell Admin** (Amendment 3's catalog-management screen, as opposed to the
  suggestion UI itself, which the Documents section already covers — `CrossSellAdmin.jsx`,
  top-level nav item)
- **Sports & Scope Admin** (`SportsScopeAdmin.jsx`, top-level nav item — master-data
  config for the sport/scope catalogs, Director-only)

Two more exist as embedded panels rather than top-level screens, and the existing
handbook doesn't mention either:
- **Messages Panel** (Amendment 8 — `MessagesPanel.jsx`, opened per-document from Cost
  Sheet/Estimate/Quotation rows in `Documents.jsx`; carries the AI "Draft with AI"
  message action)
- **Purchase Orders** (embedded in `CostSheetBuilder.jsx` via `PurchaseOrdersPanel.jsx`)

Two existing entries are now inaccurate/incomplete for what those screens actually do
today:
- **Documents** — doesn't mention the Quotation's AI-assisted **Cover Note** (Amendment
  13: draft with AI, human reviews and saves, appears on the Quotation PDF)
- **Reports** — doesn't mention the AI **summary** button, or the **Download
  Excel**/**Download PDF** export buttons that replaced the old raw-JSON view
  (Amendment 13, PR #68) — this is the screen the Director specifically asked to be
  export-only rather than showing "backend process."

**Hindi terms are entirely absent** from `handbookData.js` and `Help.jsx` — zero
occurrences of any Hindi or transliterated term, despite the register explicitly naming
"labour, material, dhanda" as the team's own vocabulary.

**Version marker**: the UI currently prints "Section 4 · v1" (Quick Start tab) and
"Section 5 · v2" (Full Handbook tab) inline. No `v3` exists yet.

### Proposed spec

1. **Add six `FULL_HANDBOOK` entries** (same shape as existing ones — what/fields/
   whenMissing/watch, worked example where a real one exists) for: All Projects, All
   Estimates, All Quotations, Vendors Admin, Price Requests, Cross-Sell Admin, Sports &
   Scope Admin. Messages Panel and Purchase Orders are proposed as **sub-bullets on their
   parent screen's existing entry** (Documents, and Cost Sheet Builder respectively)
   rather than standalone entries, since neither is independently nav-reachable — flagged
   as an open call below in case the Director wants them broken out instead.

2. **Update the two stale entries** — Documents gains a note on the AI cover-note draft
   flow (draft → human review → save, never auto-sent); Reports gains a note on the AI
   summary button and the Excel/PDF export buttons, replacing any lingering implication
   that raw report content is shown on-screen.

3. **Weave in Hindi terms** the register itself already named — "labour" alongside
   "mazdoori," "material" alongside "saaman/samagri," "dhanda" where the copy refers to
   the business generally — in the Estimator Guide and Quick Start body text specifically
   (the daily-use sections), not forced into every FAQ answer. **Open decision below**:
   this spec proposes using only the terms the register itself already named, rather than
   inventing additional ones, since guessing at the team's actual working vocabulary
   risks getting it wrong in a document meant to speak their language correctly.

4. **Extend the guides** — Director/Admin Guide gains references to All Quotations (as
   the concrete home of Amendment 6b's "review all quotations" scope), Vendors
   Admin/Price Requests (the procurement bridge), and Sports & Scope Admin. Estimator
   Guide gains a Messages Panel mention alongside its existing Cost Sheet/Rate Sheet
   sections, since Sales/PM are the roles who actually send client messages.

5. **Version bump**: "Section 5 · v2" becomes "Section 13 · v3" on the Full Handbook tab
   (Quick Start tab's "Section 4 · v1" is unaffected — that step-by-step content hasn't
   changed). Update `Help.jsx`'s own top comment to record this as the wave that closed
   the gap Annexure-2 v1.11 flagged.

**Format**: unchanged — same print-friendly pattern (`window.print()`, `@media print`),
each tab printable independently.

**Acceptance criteria:** every screen reachable from the current top-level nav has a
Full Handbook entry (or is explicitly folded into its parent, per the open call below);
Documents and Reports entries reflect what those screens actually do today; at least the
three register-named Hindi terms appear in the Quick Start/Estimator Guide copy;
Director/Admin Guide references every Director-only screen shipped through Amendment 13;
each tab still prints cleanly to its own page(s); the version marker reads "Section 13 ·
v3."

### Open decisions — need Director input before implementation

1. **Messages Panel / Purchase Orders — sub-bullet or standalone entry?** Proposed as
   sub-bullets (see above) since neither is independently nav-reachable. If the Director
   wants them as their own Full Handbook sections regardless, that's a small scope
   addition, not a rework.
2. **Hindi terms — scope.** Proposed to use only "labour/mazdoori," "material/saaman,"
   and "dhanda" (the register's own examples), applied to the Quick Start and Estimator
   Guide sections only. If the Director wants broader or different vocabulary (e.g. terms
   specific to this team that aren't in the register), that needs to come from the
   Director directly rather than be guessed at here.
3. **Education screen** (`Education.jsx`, a placeholder per Amendment 12) and secondary
   panels (Attachments, Custom Notes, Client Signatories, Role & Permissions viewer,
   Tender Mode, the Tools basic calculator) are proposed as **out of scope** for this
   wave — none are new since PR #34 except the basic calculator (Amendment 12), which is
   minor enough to fold into a one-line mention under Tools rather than its own entry.
   Flagging in case the Director disagrees on any of these.

---

## Approval

Amendment 10 (handbook v3 — new screens, stale-entry updates, Hindi terms): ☑ Approved —
"approve the handbook spec, answer the open decisions" (16 September 2026)

Decision 1 (Messages Panel / Purchase Orders): ☑ Resolved as proposed — sub-bullets on
their parent screen's existing entry (Documents, Cost Sheet Builder), not standalone
Full Handbook sections.
Decision 2 (Hindi terms — scope): ☑ Resolved as proposed — the register's own three
named terms only (labour/mazdoori, material/saaman, dhanda), applied to the Quick Start
and Estimator Guide sections.
Decision 3 (Education / secondary panels / Tools calculator): ☑ Resolved as proposed —
out of scope for this wave, except a one-line mention of the basic calculator under the
Tools reference in the relevant guide.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 16 September 2026
