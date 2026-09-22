# Section 42 — Spec Doc

## Amendment No. 36 — Nav Shell + Dashboard Shell (CRM Restructure, Phase 1 of the Header Index)

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 36 (registered 22
September 2026, from `docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`
Sections D/E). This is Phase 1 of the 9-step header-by-header build index — the nav shell
and the Dashboard's visual shell only. It does **not** build Opportunities, Follow-ups, or
Payments as real capabilities — those are Phases 4, 5, and 7 respectively, each their own
future amendment.

### Current state

`frontend/src/App.jsx:129-213` — top nav, dropdown groups: Dashboard / Quotation /
Projects / Client / Vendor / Tools / Reports / Admin / Education (full detail: this
project's nav audit, folded into `PROJECT-BLUEPRINT.md` Section 3 and the plan doc's
Section D0).

`frontend/src/Dashboard.jsx` — 5 static tiles (Open projects, Pending estimates, Pending
quotations, Overdue clients, Won this month) + a flat recent-projects list, confirmed by
direct read, no charts, no trend data.

Confirmed absent from the schema (`PROJECT-BLUEPRINT.md` Section 6): any `Opportunity`
entity, any pipeline-stage tracking, any follow-up/reminder field, any forward-looking
payment due-date field. None of this amendment's UI work can be backed by real data yet.

### Proposed spec

1. **Replace the top nav with a left sidebar.** Confirmed items, each routing to its
   existing real screen (re-homed, not rebuilt, in this phase):
   - **Overview** -> the new Dashboard shell (see below)
   - **Leads & Clients** -> today's `ClientsAdmin.jsx` screen, unchanged
   - **Quotations** -> today's Quotation screens, unchanged
   - **Projects** -> today's Projects/Documents flow, unchanged
   - **Team & Access** -> today's User Management + Role Permissions Viewer, unchanged
2. **Placeholder items for not-yet-built headers**, visually present per the CRM
   reference but functionally inert until their own later phase ships:
   - **Opportunities** -> a "Coming soon" placeholder screen
   - **Follow-ups** -> a "Coming soon" placeholder screen
   - **Payments** -> a "Coming soon" placeholder screen
3. **A temporary "More" item** at the bottom of the sidebar holding Vendor, Tools,
   Reports, Admin, and Education exactly as they work today (unchanged screens, just
   relocated one level deeper) -- keeps every current capability reachable without
   forcing a placement decision that belongs to Phase 8. Removed once Phase 8 resolves
   where each of these five actually lands.
4. **Dashboard shell** matching the CRM reference's layout (KPI tile row, a chart panel,
   a pipeline/breakdown panel, a records table, an action-items panel), built with:
   - **Real data** for any tile backed by something that already exists today (e.g.
     Pending quotations, Active/open projects -- reusing today's existing dashboard
     query logic, not new aggregation).
   - **Explicit "not yet available" empty states** -- not a literal "0" -- for any tile
     whose data doesn't exist yet (Open opportunities, Follow-ups due, Payments
     overdue), so nobody reading the dashboard mistakes an unbuilt feature for a real
     zero count. Exact copy: e.g. "Opportunities -- coming soon" rather than "0".
5. No backend changes beyond what's needed to serve the existing, already-real dashboard
   tiles through the new layout. No new tables, no new endpoints for Opportunities/
   Follow-ups/Payments in this amendment.

**Acceptance criteria:**
- Every screen reachable today remains reachable after this ships -- nothing hidden or
  removed, confirmed by clicking through the full old nav list against the new one.
- Opportunities/Follow-ups/Payments/Payments-overdue never display a fabricated number;
  they clearly state the capability doesn't exist yet.
- Pending quotations and Active projects tiles on the new Dashboard show the same real
  counts the old Dashboard showed, sourced from the same backend logic.
- Sidebar and Dashboard visually follow this app's existing brand system (Amendment 1:
  dark theme, gold `#c9a227` accent), not a wholesale re-skin to the reference's own
  color palette -- see Open Decision 1.

### Open decisions

1. **Visual theme: keep NestaPrime's existing gold-accent dark theme (proposed
   default), or adopt the reference mockups' own color palette (navy/teal panels,
   different accent)?** Proposed default: **keep the existing brand system** --
   Amendment 1 already established this app's visual identity; the reference images are
   being used as a *layout/structure* reference (sidebar, tile row, chart placement),
   not a re-brand. A full color/theme change is a separate decision, not implied by
   choosing this layout.
2. **Empty-state treatment for not-yet-built tiles: plain text ("Opportunities --
   coming soon," proposed default) vs. a greyed-out/disabled tile styling vs. hiding the
   tile entirely until its phase ships?** Proposed default: **plain text, tile stays
   visible** -- keeps the full intended layout visible from day one (matches the
   shell-first intent) without ever implying a real zero.
3. **Does the temporary "More" menu preserve the exact old dropdown groupings (Vendor /
   Tools / Reports / Admin / Education as five separate sub-groups), or flatten them
   into one list?** Proposed default: **keep the exact old groupings** -- lowest-risk,
   nothing about how these screens are organized changes in this phase, only their
   entry point moves.

## Approval

☑ Approved — "approve as proposed, all decisions" (22 September 2026).

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
