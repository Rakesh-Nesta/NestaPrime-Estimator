# Section 49 — Amendment No. 43 Spec

## Amendment No. 43 — Follow-ups (Header Index Step 4)

### Registered scope
Build a real "Follow-ups" screen (Section E step 4 of
`docs/planning/2026-09-Sales-Experience-and-Dashboard-Plan.md`), and wire the two
Dashboard placeholders that are already explicitly earmarked for it in their own code
comments, so the Sidebar/tab-strip nav item can lose its "Soon" badge.

### Current state (file:line evidence)
- `Client` (`backend/app/models/client.py`) carries `next_follow_up_date` (Date, nullable)
  and `follow_up_note` (String(200), nullable) since Amendment 42, and no owner/assigned-rep
  field of any kind (re-confirmed by grep, zero matches for "owner"/"assigned_to"/"rep_id").
- `GET /clients` (`backend/app/api/clients.py:152-157`) already returns every client via
  `ClientOut`, which already includes `next_follow_up_date`/`follow_up_note`
  (`clients.py:103-104`) -- unfiltered, unsorted, no query params.
- `Sidebar.jsx:131` -- Follow-ups nav item: `muted: true, badge: "Soon"`.
- `Dashboard.jsx:151` -- tab strip already has a "Follow-ups" tab wired to
  `onDrillDown("followups", {})`.
- `Dashboard.jsx:199` -- KPI tile is a `ComingSoonTile label="Follow-ups due"`, not real
  data. `Dashboard.jsx:52-53`'s own header comment names it as backend-less.
- `Dashboard.jsx:279-282` -- "Your next moves" panel is a `ComingSoonPanel` whose
  description literally reads "Overdue follow-ups and action items, with owner and due
  date -- lands with Follow-ups (Phase 4)."
- `App.jsx:273-278` -- `screen === "followups"` renders a generic `ComingSoon` placeholder.
- `backend/app/api/dashboard.py:29-34` -- `DashboardSummary` has four computed count
  fields (`open_projects_count`, `pending_estimates_count`, `pending_quotations_count`,
  `overdue_clients_count`) plus `won_this_month_total`; no `followups_due_count`.
  `get_dashboard()` (`dashboard.py:53-58`) is role-gated to
  `sales`/`pm`/`director`/`procurement`/`site_engineer`/`ca_tax`.

### Proposed spec
1. **New `followups_due_count` field on `DashboardSummary`** (`dashboard.py`), computed
   alongside the existing counts as: clients where `next_follow_up_date` is not null and
   `next_follow_up_date <= today` (i.e. due today or overdue -- matches the "due/overdue"
   framing already used in `App.jsx:276`'s placeholder copy). Wire `Dashboard.jsx:199`'s
   tile to this real value via the existing `realTiles`/`CountUpValue` pattern used by the
   other two real tiles, dropping `ComingSoonTile` for this one.
2. **Real "Follow-ups" screen**, replacing the `ComingSoon` placeholder at
   `App.jsx:273-278`. Reuses `GET /clients` (no new backend endpoint for the list itself)
   and, client-side: filters to clients with `next_follow_up_date` set, sorts
   soonest-first (most overdue at the top), and renders each row as client name,
   `next_follow_up_date` (red text if overdue, matching `ClientsAdmin.jsx`'s existing
   overdue-red convention from Amendment 42), and `follow_up_note`. Each row links/drills
   into `ClientsAdmin.jsx`'s existing inline follow-up editor (Amendment 42) to update or
   clear the date -- no duplicate edit UI is built here.
3. **"Your next moves" panel** (`Dashboard.jsx:279-282`) becomes a real list: the same
   due/overdue client set as the Follow-ups screen, capped to a short preview (proposed:
   5 rows, "View all →" linking to the full Follow-ups screen), showing client name, date,
   and note. The placeholder text's "with owner" phrase is dropped -- there is no owner
   field on `Client` yet, and this register's data-honesty principle (established at
   Amendment 41/42) rules out fabricating one.
4. **Remove the "Soon" badge** from `Sidebar.jsx:131` and un-mute that nav item, now that
   `followups` routes to a real screen instead of the generic `ComingSoon` placeholder.
5. Role gate for the new screen and the `followups_due_count` field matches the existing
   Dashboard gate (`sales`/`pm`/`director`/`procurement`/`site_engineer`/`ca_tax`) --
   no new role logic introduced.

### Explicitly out of scope
- Per-rep/personalized "my follow-ups" filtering -- blocked on `Client` (or the future
  `Opportunity`) having an owner field, which does not exist yet. This ships as an
  org-wide view, same honesty boundary already documented at Amendment 42's registration.
- Any change to the Lead/Client/Opportunity data model itself -- that is Section E step 5
  (Opportunities), already Director-scoped separately with its own locked design input
  (Lead vs. Client split, "Add Enquiry" entry point, mandatory follow-up date discipline).
- Notifications, reminders, or any push/email/WhatsApp alerting on due follow-ups -- this
  amendment is a screen and two Dashboard wiring changes, not an alerting system.

### Acceptance criteria
- `GET /dashboard` response includes `followups_due_count`, correctly counting clients
  with `next_follow_up_date <= today`, verified by a new backend test seeding clients with
  past, today, future, and null follow-up dates.
- Dashboard's "Follow-ups due" tile shows the real count (with `CountUpValue` animation,
  consistent with the other two real tiles), not a `ComingSoonTile`.
- Navigating to "Follow-ups" (Sidebar or tab strip) shows a real list of clients with a set
  follow-up date, soonest/most-overdue first, no "Soon" badge remaining on the nav item.
- "Your next moves" panel on Dashboard shows real upcoming/overdue follow-ups (client name,
  date, note only -- no fabricated owner column), with a working link to the full screen.
- No existing Dashboard or Client Admin test regresses; new tests cover the
  `followups_due_count` computation.

### Open decisions (proposed defaults)
1. **"Due" window for the count and the tile**: proposed default is `<= today` (due today
   counts as due, not just strictly overdue) -- matches how `overdue_flag` and
   `ClientsAdmin.jsx`'s red-text convention already treat dates.
2. **"Your next moves" preview row cap**: proposed default is 5 rows, consistent with how
   tight the existing "Recent Projects" list already runs on this Dashboard.
3. **Whether the Follow-ups screen needs its own route/component or can be a filtered view
   inside `ClientsAdmin.jsx`**: proposed default is a new lightweight `Follow-ups.jsx`
   component (reusing `api.js`'s existing `getClients`/`updateClientFollowUp` helpers)
   rather than overloading `ClientsAdmin.jsx`, since the Follow-ups screen's job (a
   triage queue) is different from the Client Admin screen's job (a client register).

### Approval
☑ Approved as proposed, all decisions
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 23 September 2026
