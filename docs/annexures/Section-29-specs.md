# Section 29 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same third proactive gap audit as Section 28,
spot-verified against the live code before being registered as Amendment No. 23.

---

## Amendment No. 23 — Document/PO Number Generation Races Under Concurrent Creation

**Registered scope (Annexure 2, §Amendment 23):** `_generate_project_no` and
`_po_number` compute the next sequence number in Python with no lock, so two concurrent
creations can compute the same number and the second dies with an unhandled
`IntegrityError`.

### Current state (verified against `backend/app/api/projects.py:36-49` and
`backend/app/api/purchase_orders.py:27-33`, direct read)

```python
def _generate_project_no(db: Session) -> str:
    yymm = datetime.now(UTC).strftime("%y%m")
    prefix = f"P-{yymm}-"
    existing = db.query(Project.project_no).filter(Project.project_no.like(f"{prefix}%")).all()
    max_seq = 0
    for (project_no,) in existing:
        try:
            max_seq = max(max_seq, int(project_no.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}{max_seq + 1:04d}"
```

`_po_number` follows the identical shape (count instead of max, same race). Both rely
entirely on the column's `unique=True` constraint (`Project.project_no`,
`PurchaseOrder.po_no`, both confirmed present in the models) to catch a collision --
there is no row lock, no database sequence, and no retry. Two PMs creating a project in
the same moment (or two POs raised on the same Cost Sheet close together) can both read
the same existing-numbers set before either commits, both compute the identical next
number, and the second request's `db.commit()` raises an unhandled `IntegrityError`,
surfacing as a raw 500 to whichever PM/Procurement staff lost the race -- not a graceful
retry, not a real distinct number.

### Proposed spec

1. **Catch-and-retry on the unique-constraint violation**, rather than a schema change:
   wrap the existing generate-then-insert logic in both `create_project`
   (`projects.py`) and `create_purchase_order` (`purchase_orders.py`) in a small retry
   loop (e.g. up to 3 attempts) that catches `sqlalchemy.exc.IntegrityError` specifically
   on the relevant unique constraint, rolls back, regenerates the number (which will now
   see the just-committed row and compute the next one correctly), and retries the
   insert. This requires no migration and no new table, and turns the race from a
   user-visible 500 into invisible-to-the-user correct behavior in the rare case it's
   actually hit.
2. **No change to the number *format* or the existing prefix/sequence logic** -- only
   the failure path when a collision occurs.
3. **Scope limited to these two generators** -- `_generate_project_no` and `_po_number`
   are the only two identified with this exact pattern; no other document-numbering
   function in this codebase was found to share it (Cost Sheet/Estimate/Quotation
   numbers are derived from the Project's own `project_no`, not independently
   generated).

**Acceptance criteria:** simulating two near-simultaneous project (or PO) creations
(e.g. in a test, opening two overlapping DB transactions that both read the same
"existing numbers" state before either commits) results in both succeeding with two
distinct, correctly-sequential numbers, never a 500; the normal, non-concurrent case is
completely unaffected in behavior or number format.

### Open decisions — need Director input before implementation

1. **Confirm catch-and-retry (option proposed above) over a dedicated sequence-counter
   table** -- the retry approach is simpler and needs no migration, but a dedicated
   `sequence_counters` table with a locked `UPDATE ... RETURNING` would be a more
   conventionally "correct" fix for high-concurrency systems. Given this app's actual
   scale (a small internal team, not high-volume concurrent creation), the retry
   approach is proposed as sufficient. Confirm, or specify the heavier alternative.
2. **Retry count** -- proposed: 3 attempts before giving up and surfacing a real error
   (an actual, unrecoverable failure at that point, not just contention). Confirm or
   specify a different number.

---

## Approval

Amendment 23 (document/PO number generation race fix): ☑ Approved — "approve as
proposed, all decisions" (19 September 2026)

Decision 1 (catch-and-retry vs. dedicated sequence table): ☑ Resolved as proposed.
Decision 2 (retry count, proposed 3): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
