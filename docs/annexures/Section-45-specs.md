# Section 45 — Spec Doc

## Amendment No. 39 — Scope Checklist Has No Bulk "Not Applicable" Control

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 39.

### Current state

`frontend/src/ScopeChecklist.jsx` (full file read for this spec): 30 items across 6
category groups (Civil, Electrical, Water, External, Services, Maintenance --
`GROUP_LABELS`/`GROUP_ORDER`, lines 4-13), each toggled individually via `handleToggle`
(lines 32-46). All items start **unchecked** (`selections` loads empty until explicitly
added) -- unchecked already means excluded by design (line 85's own copy: "Unchecked
items are excluded"). So the real friction isn't clearing everything (already the
default) -- it's the opposite and the in-between cases: a project that needs *most* of
one category (e.g. every Electrical item) still requires checking each box one at a time,
and there is no way to bulk-confirm a whole category as reviewed-and-excluded either.

### Proposed spec

1. Each category section (the 6 group cards, `ScopeChecklist.jsx:91-107`) gains two small
   text-link controls next to its group heading: **"Select all"** and **"Clear all"**,
   scoped to that group's items only.
2. "Select all" calls `addProjectScopeItem` for every currently-unchecked item in that
   group; "Clear all" calls `removeProjectScopeItem` for every currently-checked item in
   that group -- same underlying API calls `handleToggle` already makes, just looped
   per-group instead of requiring one click per checkbox.
3. No new backend endpoint, no new "reviewed" state -- this stays within the existing
   checked/unchecked model. A bulk "confirm as reviewed" distinct from "confirm as
   excluded" would need a new field this amendment does not add.

**Acceptance criteria:**
- Clicking "Select all" on a group checks every item in that group only, leaving other
  groups untouched.
- Clicking "Clear all" on a group unchecks every item in that group only.
- The existing per-item checkboxes continue to work individually exactly as today.
- The "N of 30 included" summary line updates correctly after a bulk action.

### Open decisions

1. **Per-group controls (proposed default) vs. one single global "select all"/"clear
   all" for the whole 30-item list?** Proposed default: **per-group** -- a single global
   control mostly isn't useful (a real project rarely wants literally everything on or
   off at once; it wants a category at a time), and per-group scoping directly matches
   the layout already on screen.
2. **Confirmation before a bulk action, given it can touch several items at once?**
   Proposed default: **no confirmation dialog** -- every individual toggle already saves
   immediately with no confirmation, and a bulk action within one visible group is no
   higher-stakes than that existing pattern.

## Approval

☐ Approved — pending Director decision.

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
