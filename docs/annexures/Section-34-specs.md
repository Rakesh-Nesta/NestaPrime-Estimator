# Section 34 — Draft Specifications for Director Approval

**Date: 20 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same fifth proactive gap audit as Sections 32-33,
spot-verified against the live code before being registered as Amendment No. 28.

---

## Amendment No. 28 — Dashboard "Open Projects" Permanently Misclassifies Restarted Projects

**Registered scope (Annexure 2, §Amendment 28):** the dashboard's Open Projects tile
excludes a project forever once any Quotation on it reaches WON/LOST, even if a newer,
currently-active Quotation now exists on the same project. A related, broader gap: no
dashboard tile excludes calibration/test-project data, despite the register's own text
calling for one.

### Current state (verified against `backend/app/api/dashboard.py:62-70`, direct read)

```python
closed_project_ids = (
    db.query(Quotation.project_id)
    .filter(Quotation.status.in_([QuotationStatus.WON, QuotationStatus.LOST]))
    .distinct()
)
open_projects_count = (
    db.query(Project).filter(~Project.id.in_(closed_project_ids)).count()
)
```

This excludes a project the moment *any* of its Quotations has ever reached WON/LOST --
not whether the project currently has live, in-progress work. Once Amendment 26 makes
re-bidding a lost project actually possible (today it crashes), this bug means the
newly re-bid project would still never appear in Open Projects, defeating the point of
being able to restart it.

Separately: a repo-wide grep for `is_calibration`/`is_test`/`calibration` across
`backend/app/models` and `backend/app/api` returns zero matches -- no such flag exists
anywhere, despite this register's own Amendment 4 refinement text ("so real client work
isn't crowded by validation data") and Note R1's Mathura/Noida/Bathinda projects being
real, recreated database rows.

### Proposed spec

**Part A — fix the "ever closed" logic:**
1. A project counts as closed only if **every** Quotation on it (not *any*) has reached
   WON/LOST, and it has at least one Quotation at all:
   ```python
   closed_project_ids = (
       db.query(Project.id)
       .join(Quotation, Quotation.project_id == Project.id)
       .group_by(Project.id)
       .having(func.bool_and(Quotation.status.in_([QuotationStatus.WON, QuotationStatus.LOST])))
   )
   ```
   (exact SQL construction to be finalized at implementation time -- the `bool_and`
   aggregate, or an equivalent `NOT EXISTS` subquery excluding projects with any
   non-terminal Quotation, are both valid; either produces the same correct result: a
   project with a live, currently-active Quotation is never counted as closed,
   regardless of its history.)
2. A project with no Quotations at all is never counted as closed (matches today's
   behavior for that case -- unaffected by this fix).

**Part B — add a calibration/test-project exclusion:**
3. New nullable `Project.is_calibration: bool` column (default `False`), added via
   migration.
4. `ProjectCreate` gains an optional `is_calibration: bool = False` field, settable only
   by Director/PM at creation time (or via a dedicated small PATCH, Director-only, for
   flagging an existing project after the fact -- see Decision 3 below).
5. All three dashboard tiles (`open_projects_count`, `pending_estimates_count`,
   `pending_quotations_count`) add `.join(Project).filter(Project.is_calibration.is_(False))`
   (or equivalent) to exclude flagged projects.
6. **The existing Mathura/Noida/Bathinda Note R1 projects are not automatically
   detected or flagged by this change** -- there's no reliable code-level signal
   distinguishing them from real client work (they were deliberately created as
   realistic, real-shaped data). Retroactively flagging them is a manual, one-time data
   correction for whoever implements this, using the project records Note R1's own
   audit trail already identifies by name/client.

**Acceptance criteria:** a project with one Lost Quotation and one newer, still-active
Quotation counts as Open; a project where every Quotation is WON/LOST still counts as
closed exactly as today; a project flagged `is_calibration=True` never contributes to
any of the three dashboard tiles; an unflagged project is completely unaffected by Part
B.

### Open decisions — need Director input before implementation

1. **Confirm Part A's "all Quotations closed, not any" logic** as the fix.
2. **Confirm Part B's `is_calibration` flag** as the mechanism, rather than some other
   approach (e.g. a naming convention, a separate "test mode" toggle spanning more than
   just Projects). Proposed as the smallest, most direct fix matching what the register
   already asked for.
3. **Who can set/change `is_calibration`, and when** -- proposed: settable at creation
   time by PM/Director (matching `create_project`'s existing role gate), plus a
   Director-only PATCH for flagging an existing project after the fact (needed for the
   Note R1 backfill in point 6 above). Confirm, or restrict further (e.g.
   Director-only even at creation).

---

## Approval

Amendment 28 (dashboard Open Projects fix + calibration filter): ☑ Approved — "approve
as proposed, all decisions" (20 September 2026)

Decision 1 (all-Quotations-closed logic): ☑ Resolved as proposed.
Decision 2 (is_calibration flag as the mechanism): ☑ Resolved as proposed.
Decision 3 (who can set is_calibration, and when): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 20 September 2026
