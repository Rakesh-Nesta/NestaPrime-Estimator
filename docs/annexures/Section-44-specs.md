# Section 44 — Spec Doc

## Amendment No. 38 — Create-Cost-Sheet Form Stays Live After a Sheet Already Exists

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 38.

### Current state

`frontend/src/Documents.jsx:451-477`: the create-cost-sheet input/button section is
gated only on `role !== "sales"` (line 451). Neither the cost input (453-459) nor its
wrapping section is hidden once an active Cost Sheet exists for the project -- the button
(468-474) is only `disabled={!!active}` (line 470).

### Proposed spec

1. Wrap the create-cost-sheet section's existing condition with an additional
   `&& !active` check, so it renders **only when no Cost Sheet exists yet** for the
   project -- same existence-based gating the existing-sheet action row already uses
   one section below it.
2. No change to the existing-sheet display, the Revise flow, or any backend behavior --
   frontend-only visibility fix.

**Acceptance criteria:**
- Opening Documents for a project with no Cost Sheet yet: the create form is visible,
  exactly as today.
- Opening Documents for a project that already has a Cost Sheet: the create form is
  gone entirely, not just disabled; only the existing-sheet section shows.
- The skip-request flow (adjacent to this section) is unaffected.

### Open decisions

None -- this is a narrow, single-condition visibility fix with no meaningful alternative
approach.

## Approval

☑ Approved — "approve as proposed, all decisions" (22 September 2026).

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
