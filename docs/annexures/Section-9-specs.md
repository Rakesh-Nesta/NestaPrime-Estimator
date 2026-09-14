# Section 9 — Draft Specification for Director Approval

**Date: 14 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

---

## Amendment No. 6b — Admin Reviews All Quotations and Daily Activity

**Registered scope (Annexure 2, §2, Amendment No. 6):** "6b: admin reviews all
quotations and daily activity." The other two thirds of Amendment 6 are already
shipped — 6a (read-only Role & Permissions viewer) and 6c (report period presets) —
but 6b itself was never carried into a section and is still a real gap.

### Current state
Confirmed by a full repo search (backend `app/api`, frontend `src`):

- **No cross-project quotations view exists.** The only quotation-listing endpoint is
  `GET /projects/{project_id}/quotations` (`backend/app/api/pdf_documents.py`) — scoped
  to one project. The only quotations UI is `Documents.jsx`'s per-project list. There is
  no unscoped `GET /quotations`, no `AllQuotations`/`QuotationsList` component, no
  `/quotations` route anywhere.
- **"Daily activity" is already covered**, just not by anything named 6b: Amendment 4
  shipped the Dashboard's plain-language Recent Activity feed and the raw-diff Audit
  Log, both already Director/Admin-only per Amendment 4's admin/user separation. No new
  build needed for that half.
- **Reports (6c) doesn't substitute for a quotations review screen.** `Reports.jsx` /
  `reports.py` support exactly two report types: **Pipeline** (aggregate counts/totals
  by status — not a line list a Director can scan) and **Margin Performance**
  (Director/PM-only; does list individual quotations with cost/selling/margin, but only
  those *released* within the chosen period, no client name, and it's a generated
  point-in-time report, not a live filterable table). A Director wanting to check "what's
  outstanding right now" — draft, sent, or won/lost, across every project, any period —
  has no screen for it today.

### Proposed spec

**1. New unscoped endpoint** — `GET /quotations` (Director/Admin only, matching the
Amendment 4 admin/user separation already enforced on Master Settings, Audit Log, etc.).
Reuses the existing `QuotationOut` / `_quotation_to_out` shape from `pdf_documents.py`
so the payload matches what `Documents.jsx` already renders per-project — no new
response shape to design. Filters: `status`, `project_id`, `client_id`, `date_from`,
`date_to`; paginated, newest first by default.

**2. New "All Quotations" screen** — a table: document no., project, client, sport,
status, selling price, date, with the same status filter chips the per-project view
already uses. Each row drills through to that project's existing Documents screen
(reusing navigation, not rebuilding the per-project detail view). Lives under the
Management nav group Amendment 4 already established (alongside Reports), not folded
into Reports itself — Pipeline/Margin stay generated report *artifacts*, this stays a
live *browse* screen; conflating the two would make Reports' own period-preset filters
ambiguous (a report period vs. a live table filter are different interactions).

**3. No new data.** This is a read view over quotations that already exist — no schema
change beyond the query itself, no new document type, no change to how a Quotation is
created, priced, or released.

**Acceptance criteria:** A Director opens "All Quotations" from the Management nav
group and sees every quotation across every project, newest first; filtering by status
(e.g. "sent") narrows the table without a page reload; filtering by client or a date
range works the same way; clicking a row opens that project's Documents screen at the
matching quotation; a Sales or PM-role user does not see this nav item at all (same
gate as Master Settings/Audit Log).

### Decision — Director-approved (14 September 2026)

**Decision A — does this screen need its own export (CSV/PDF), or is browse-and-drill
enough for this wave?** **Director decision: add CSV/PDF export this wave too** (not the
Recommended browse-and-drill-only option). The table gets its own export control on top
of the acceptance criteria above — same filtered result set the screen is currently
showing (status/project/client/date), not a separate unfiltered dump. This is additive
to §2 of the proposed spec, not a replacement for it.

---

## Approval

Amendment 6b: ☑ Approved
Decision A (export): ☑ Add CSV/PDF export this wave too

Director Name: ______________________ Signature: ______________________ Date: 14 September 2026

Prepared by: R. Patni (with AI development assistance) | Date: 14 September 2026
