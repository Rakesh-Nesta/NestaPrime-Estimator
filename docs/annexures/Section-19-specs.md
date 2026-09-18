# Section 19 — Draft Specifications for Director Approval

**Date: 18 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: the one item from Amendment 4's 12 September findings that Amendment 12's
nav/dashboard restructure never touched — "the Clients page itself needs a per-client
project list, not just the global recent-projects list on the dashboard." Confirmed
still open by re-checking the current code (18 September), not assumed from the older
register text.

---

## Amendment No. 4, continued — Per-Client Project List

**Registered scope:** from `ClientsAdmin.jsx`, see a given client's own projects,
without going to Projects and typing the client's name into free text.

### Current state

Unlike Section 18, this is a pure assembly task, not new content — the data already
exists and already drives real Cost Sheets/Quotations:

- `Project.client_id` is a real foreign key (`backend/app/models/project.py`); every
  project already belongs to exactly one client.
- `GET /projects` (`backend/app/api/projects.py:239`) already joins `Client` and
  supports `search`/`status` query params, ordered by `created_at desc`, open to the
  same five roles (`sales`, `pm`, `director`, `procurement`, `site_engineer`) plus
  `ca_tax` — it just has no `client_id` filter param yet.
- `ClientsAdmin.jsx` renders one row per client (flags, consent controls) with no
  project-related content at all.
- `AllProjects.jsx` (Amendment 12) already renders a project list with status
  badges and an "Open →" link into `App.jsx`'s `handleOpenProject` — the exact
  row-rendering shape a per-client list can reuse.

### Proposed spec

1. **`GET /projects` gains an optional `client_id` query param**, filtering
   `Project.client_id == client_id` in addition to the existing `search`/`status`
   filters — additive, no change to existing callers, same role gate.
2. **`ClientsAdmin.jsx`'s per-client row gains a "Projects" expand/link** showing that
   client's own projects (project number, status badge, "Open →"), fetched via
   `listProjects(token, { client_id: client.id })` — same row shape as
   `AllProjects.jsx`, reused rather than redesigned. Collapsed by default so the
   existing flags/consent screen doesn't get visually heavier for clients no one is
   drilling into.
3. **No new content, no new tables** — this is wiring an existing relationship into a
   screen that doesn't show it yet, the same category of change as Amendment 12 itself.

**Acceptance criteria:** opening a client on the Clients screen and expanding
"Projects" shows exactly that client's own projects, correctly excluding every other
client's; clicking "Open →" on one of them resumes into that project the same way
`AllProjects.jsx`'s own link does; a client with no projects yet shows "No projects
yet" rather than an empty list with no explanation; the existing flags/consent controls
are unchanged.

### Open decisions — need Director input before implementation

1. **Expand-in-place vs. a separate drill-through screen.** Proposed: expand-in-place
   (a collapsible section on the existing client row), since the list is typically
   short per client and a separate screen would just duplicate `AllProjects.jsx` with
   an extra click.
2. **Default state** — collapsed by default (proposed, keeps the existing screen's
   density unchanged for the common case of just editing a client's flags) vs. always
   expanded.

---

## Approval

Amendment 4 continuation (per-client project list — `GET /projects` gains a
`client_id` filter, `ClientsAdmin.jsx` gains an expandable per-client project list
reusing `AllProjects.jsx`'s row shape): ☐ Pending Director approval.

Decision 1 (expand-in-place, not a separate screen): ☐ Pending.
Decision 2 (collapsed by default): ☐ Pending.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 18 September 2026
