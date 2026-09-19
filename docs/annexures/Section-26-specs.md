# Section 26 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same second proactive gap audit as Section 25,
spot-verified against the live code before being registered as Amendment No. 20.

---

## Amendment No. 20 — Purchase Order Receiving Overwrites Instead of Reconciling

**Registered scope (Annexure 2, §Amendment 20):** receiving a PO line overwrites
`received_qty` rather than reconciling it against concurrent updates, and a related bug
leaves `po.status` stuck when a receipt is corrected back down.

### Current state (verified against `backend/app/api/purchase_orders.py:264-297`, full
function read)

```python
for update in payload.lines:
    line = lines_by_id.get(update.line_id)
    ...
    line.received_qty = update.received_qty          # line 287 -- plain overwrite

if all(float(line.received_qty) >= float(line.quantity) for line in lines):
    po.status = PurchaseOrderStatus.RECEIVED
elif any(float(line.received_qty) > 0 for line in lines):
    po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
# no else -- status never reverts to ISSUED               # lines 289-292
```

**Part A (overwrite):** `line.received_qty = update.received_qty` replaces the stored
value wholesale, with no row lock, no version/timestamp check, and no diff against what
was there before. The endpoint's own request shape (`ReceiveLineIn.received_qty`) is
already documented as "delivered quantity," i.e. each call states what the caller
believes the new total received-to-date is, not a delta -- which means two staff
recording separate delivery batches close together, each working from what they saw
when they last loaded the PO, can have the second call silently discard the first's
update with no conflict signal to either party. This directly feeds the Consumption
Sheet and BOM's own "Received qty"/"Balance" columns (`exports.py`), so a lost update
here is a real inventory-accuracy risk, not just a UI inconvenience.

**Part B (status doesn't revert):** the `if`/`elif` above has no `else`. Correcting a
line's `received_qty` back down to 0 (e.g. undoing a mis-entered receipt) leaves
`po.status` at whatever it was before -- stuck at `PARTIALLY_RECEIVED` even though no
material is recorded as received -- contradicting the function's own docstring ("status
derives from the lines' own received_qty vs quantity").

### Proposed spec

1. **Part B is the simpler, lower-risk fix -- do it regardless of Part A's outcome:**
   add the missing `else: po.status = PurchaseOrderStatus.ISSUED` branch, so status
   always derives cleanly from the current quantities exactly as documented.
2. **Part A needs a Director decision between two real approaches** (see Open Decisions
   below) -- this spec proposes **optimistic concurrency**: `ReceiveLineIn` gains an
   optional `expected_received_qty` field; if supplied and it doesn't match the line's
   current stored value at the moment of the write, the endpoint returns `409 Conflict`
   with the real current value, and the frontend re-fetches and asks the user to
   re-apply their entry against the up-to-date number, rather than silently overwriting.
   This preserves the existing "state the new total" semantics (no behavior change for
   the normal, non-concurrent case) while turning a silent lost update into a visible,
   recoverable conflict.
3. **Frontend change (Part A only):** `PurchaseOrdersPanel.jsx`'s receive form would
   need to capture the `received_qty` it last displayed and send it as
   `expected_received_qty`, plus a conflict-handling UI path for the new `409`.
4. **No change to the RECEIVED/PARTIALLY_RECEIVED status logic itself** beyond the new
   `else` branch in Part B -- the thresholds and role gates are correct and untouched.

**Acceptance criteria:** correcting every line's `received_qty` back to 0 reverts
`po.status` to `ISSUED`; (if Part A is approved as proposed) two receive calls against
the same line, the second based on a now-stale `expected_received_qty`, result in the
second being rejected with `409` rather than silently overwriting the first's recorded
receipt; a receive call with no `expected_received_qty` supplied (or matching the current
value) behaves exactly as it does today.

### Open decisions — need Director input before implementation

1. **How should Part A actually be fixed?** Two real options:
   - **(a) Optimistic concurrency** (proposed above) -- minimal behavior change, adds a
     `409` conflict path the frontend must handle.
   - **(b) Make `received_qty` additive** -- each call supplies a delta ("received 3
     more today") instead of a new total; simpler mental model for a warehouse-style
     "log what just arrived" workflow, but changes the field's meaning for every
     existing caller and needs the frontend rebuilt around deltas instead of totals.
   This is a genuine design choice, not just an implementation detail -- confirm (a),
   (b), or specify a preference.
2. **Confirm Part B's fix** (add the missing `else` branch) -- proposed as
   uncontroversial and separable from Part A's decision.

---

## Approval

Amendment 20 (PO receiving reconciliation + status revert): ☑ Approved — "approve as
proposed, all decisions" (19 September 2026)

Decision 1 (Part A approach -- optimistic concurrency, option (a)): ☑ Resolved as
proposed.
Decision 2 (Part B fix, add the missing `else` branch): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
