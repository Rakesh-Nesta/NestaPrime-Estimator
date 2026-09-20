# Section 31 — Draft Specifications for Director Approval

**Date: 20 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same fourth proactive gap audit as Section 30,
spot-verified against the live code before being registered as Amendment No. 25.

---

## Amendment No. 25 — Rate Sheet Excel Import Silently Discards Non-Rate Field Edits

**Registered scope (Annexure 2, §Amendment 25):** `import_rate_items` only applies
`unit`/`hsn_sac`/`vendor`/`city_of_quote`/`labour_category_id`/`is_commodity_watched`
changes when the row's `rate` also changed, silently dropping those edits otherwise and
reporting the row as "unchanged."

### Current state (verified against `backend/app/api/rate_items.py:772-795`, direct
read, full function read for context)

```python
previous_rate = float(existing.rate) if existing.rate is not None else None
if rate is not None and rate != previous_rate:
    # ... RateHistory versioning ...
    existing.rate = rate
    db.add(RateHistory(...))
    existing.unit = unit
    existing.hsn_sac = hsn_sac
    existing.vendor = vendor
    existing.city_of_quote = city_of_quote
    existing.labour_category_id = labour_category_id
    existing.is_commodity_watched = is_commodity_watched
    updated.append(existing)
else:
    unchanged += 1
```

The single `if` condition conflates two genuinely separate questions: "did the rate
change (which needs `RateHistory` versioning)" and "did *anything* about this row
change (which should mark it updated and apply the edit)." A blank Rate cell is already
a documented, intentional "leave the rate untouched" signal (line 734-737, Amendment 11
Part A) -- meaning bulk-editing only the non-rate columns while leaving Rate blank is an
explicitly supported, expected usage pattern, not an edge case. That exact pattern is
the one this bug silently breaks.

### Proposed spec

1. **Decouple "rate changed" from "anything changed"**:
   ```python
   previous_rate = float(existing.rate) if existing.rate is not None else None
   rate_changed = rate is not None and rate != previous_rate
   fields_changed = (
       rate_changed
       or existing.unit != unit
       or existing.hsn_sac != hsn_sac
       or existing.vendor != vendor
       or existing.city_of_quote != city_of_quote
       or existing.labour_category_id != labour_category_id
       or existing.is_commodity_watched != is_commodity_watched
   )
   if not fields_changed:
       unchanged += 1
       continue

   if rate_changed:
       # ... existing RateHistory versioning, unchanged ...
       existing.rate = rate
       db.add(RateHistory(...))

   existing.unit = unit
   existing.hsn_sac = hsn_sac
   existing.vendor = vendor
   existing.city_of_quote = city_of_quote
   existing.labour_category_id = labour_category_id
   existing.is_commodity_watched = is_commodity_watched
   updated.append(existing)
   ```
2. **`RateHistory` versioning behavior is completely unchanged** -- it still only fires
   when the rate itself actually changes, exactly as today. This fix only widens *which*
   rows get their other fields applied and counted as `updated`; it doesn't touch the
   rate-history/audit trail logic at all.
3. **"unchanged" now means what it says** -- a row only counts as unchanged when every
   field, not just rate, is identical to what's already stored.
4. **No frontend change** -- `RateSheet.jsx`'s import UI already just displays the
   `created`/`updated`/`unchanged`/`errors` counts this endpoint returns; those counts
   simply become accurate.

**Acceptance criteria:** importing a file that changes only `vendor` (or any other
non-rate field) for an existing row, with `Rate` left blank or unchanged, results in
that row appearing in `updated` (not `unchanged`), and the new vendor value is
persisted; a row where truly nothing differs from the current data still counts as
`unchanged`; a row where the rate *does* change continues to trigger `RateHistory`
versioning exactly as before, with no regression to the existing, correct behavior
covered by this endpoint's current tests.

### Open decisions — need Director input before implementation

1. **Confirm the decoupled `rate_changed`/`fields_changed` logic above** as the fix --
   proposed as the direct, minimal correction, changing no other behavior of the import
   endpoint.
2. **Confirm no backfill/reprocessing of past imports is needed** -- this fix only
   changes behavior going forward; any historical Excel imports that silently dropped
   edits aren't automatically corrected (their real, intended values live only in
   whatever Excel file was originally uploaded, which this app doesn't retain). Proposed:
   out of scope -- if past imports need correcting, that's a manual re-import the
   Director can now trust to work correctly.

---

## Approval

Amendment 25 (Rate Sheet import field-update fix): ☑ Approved — "approve as proposed,
all decisions" (20 September 2026)

Decision 1 (decoupled rate_changed/fields_changed logic): ☑ Resolved as proposed.
Decision 2 (no backfill of past imports): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 20 September 2026
