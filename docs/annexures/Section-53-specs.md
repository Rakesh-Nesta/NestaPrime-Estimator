# Section 53 — Amendment No. 49 Spec

## Amendment No. 49 — Quotations Header (Header Index Step 8)

### Registered scope
The Director's instruction (24 September 2026): after Amendment 40, spec the Quotations
header. Evidence is in `docs/annexures/Annexure-2.md`, Amendment No. 49; this is Gap 1 of
Amendment 48's audit. In short: the "Quotations" nav item and the Overview's "Quotations" tab
start a *new project* for everyone except the Director, the only quotation list is
Director-only, Estimates has no header, and nothing shows which lead a quotation came from.

### Proposed spec

**Part A -- Backend (small)**
1. **`GET /quotations` opens to `sales`, `pm`, `director`.** Rows for **Sales** return
   `cost_total`, `margin_percent` and `below_floor` as `null` (the same K.3 rule
   `_quotation_to_out` already applies per project); they keep `quotation_total` and
   `selling_after_discount`, which the per-project view already shows Sales. PM and Director
   rows are unchanged. The three fields become nullable in `QuotationSummaryOut`.
   `procurement`, `site_engineer`, `ca_tax` stay refused (403), as for per-project
   quotations.
2. **`GET /quotations/export` (CSV) stays Director-only and unchanged** -- it contains
   cost/margin.
3. **Each row also carries `opportunity_id` and `lead_name`** (both `null` unless the project
   was started from a Won Opportunity, via `Project.opportunity_id`). No new link is created;
   this only surfaces the existing one.
4. Existing filters (`status`, `status_group`, date range, project, client) are unchanged, so
   the "Pending" preset still matches the Overview tile's count exactly.

**Part B -- Frontend**
5. **The "Quotations" nav item and the Overview "Quotations" tab open the Quotations screen**
   for `sales`/`pm`/`director` -- they no longer start a project. They are **hidden for
   `procurement`, `site_engineer`, `ca_tax`** (nothing to show them), as Amendment 46 did for
   Leads & Clients.
6. **The screen is the existing All Quotations list, restyled** to the newer header pattern
   (`max-w-[1000px]`, breadcrumb, icon title, Back), with two tabs: **Quotations** (the
   existing All / Pending / Old pills, status and date filters, project/client search) and
   **Estimates** (the existing Estimates list, unchanged), so the two pipeline stages read as
   siblings. Rows open the project, as today.
7. **Sales sees no cost/margin/below-floor columns** (the columns are not shown, not shown
   blank). PM and Director see them as the Director does today.
8. **A "+ New project" button** on this screen (starting a quotation still begins with a
   project), plainly labelled. The Overview's existing "+ New project" button stays.
9. **A row from a Won Opportunity shows "From lead: <name>" with "Open in Opportunities ->"**;
   rows with no originating lead show nothing there.
10. **The Overview's "Pending quotations" tile becomes clickable for `sales`/`pm`** (preset
    Pending), as it already is for the Director.
11. **Phone layout:** on phones the rows render as stacked cards, not a wide table, with no
    sideways page scroll; verified at 375px and 414px (plus 768px and a desktop pass) as
    Amendment 47 was, with the same real-Chrome method.

**Sequencing (one Amendment number, two ordered PRs):** PR 1 = Part A (backend + tests);
PR 2 = Part B (frontend, depends on PR 1). Each is deployed and live-verified before the next
header starts.

### Explicitly out of scope
- Creating, releasing, sending or changing the status of a Quotation from the list (all stay on
  the project's Documents screen). No change to the quotation lifecycle or K.3 rules.
- Any new quotation content (cover letter, descriptive scope, bank details -- plan Section C).
- The CSV export for Sales/PM.
- Removing the Director's existing Admin > "All Quotations" link (left as is; can be retired
  later).
- Payments, Team & Access naming and the More-group decisions (other audit gaps).

### Acceptance criteria
- Clicking "Quotations" as Sales, PM or Director shows a list of quotations, never a new-project
  form; Procurement, Site Engineer and CA/Tax do not see the item.
- A Sales user's list, API response and screen contain no cost, margin or below-floor figure;
  a PM's and Director's do.
- The Estimates tab shows the same Estimates the existing screen does.
- A quotation from a Won Opportunity names the lead and links to Opportunities; others show no
  lead line.
- The "Pending" list count equals the Overview "Pending quotations" tile.
- At 375px and 414px the screen needs no more width than the phone has; nothing is cut off.
- The CSV export is still refused for Sales and PM.
- No existing test regresses; new tests cover the role gate, Sales stripping, PM/Director full
  rows, the lead fields, and the export staying Director-only.

### Open decisions (proposed defaults)
1. **PM sees cost/margin in the list.** Proposed: **yes** -- PM already sees them per project
   (K.3) and on the Margin report; only Sales is stripped. (Alternative: keep the list
   Sales/PM-safe and Director-only for cost/margin.)
2. **Estimates as a tab on this screen** rather than a separate sidebar item. Proposed: **tab**
   -- fewer sidebar items, and it fixes the "Estimate has no header" mismatch.
3. **Hide the item from `procurement`, `site_engineer`, `ca_tax`.** Proposed: **yes**.
4. **Show the originating lead on a quotation row** (adds two backend fields). Proposed:
   **yes** -- plan step 8 asks for exactly this link.
5. **Export stays Director-only.** Proposed: **yes**.
6. **Leave the Admin > "All Quotations" link** for now. Proposed: **yes**.
7. **A "+ New project" button on the Quotations screen.** Proposed: **yes**, so reps who used
   the old nav item to start a project still find it.

### Approval
☑ Approved — "approve as proposed, all decisions" (24 September 2026)
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 24 September 2026
