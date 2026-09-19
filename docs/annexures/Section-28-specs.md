# Section 28 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a third Director-requested proactive gap audit
against the register, spot-verified against the live code before being registered as
Amendment No. 22.

---

## Amendment No. 22 — Master Settings Override Values Are Never Validated

**Registered scope (Annexure 2, §Amendment 22):** neither a Master Setting nor a
document-scoped Override validates its value at write time, so a bad entry (typo,
out-of-range number) doesn't fail until some later document computation crashes.

### Current state (verified against `backend/app/api/settings.py` and
`backend/app/api/documents.py`, direct read)

- `SettingCreate.value: str` (`settings.py:136`) and `OverrideCreate.override_value: str`
  (`settings.py:380`) are both unconstrained strings at write time.
- `_get_effective_setting_float` (`documents.py:255-265`) does `float(override.
  override_value)` with no `try/except` -- feeds straight into the Cost Sheet's core
  cost-build chain (`site_establishment_percent`, `company_overhead_percent`,
  `contingency_percent`, `documents.py:861-910`).
- `pricing.py:324`'s `1 + gst_rate_percent / 100` divisor has no floor -- a
  `gst_rate_percent` override/setting of `-100` produces `ZeroDivisionError`.
- **Not every Setting is numeric** -- confirmed by `bulk_update_settings`
  (`settings.py:184-230`), which explicitly catches `ValueError` and skips non-numeric
  rows with the comment "non-numeric setting values aren't bulk-adjustable" (e.g.
  company-detail text fields, T&C clauses live as Settings too, per Amendment 14). This
  rules out a blanket "every Setting/Override value must be numeric" validation at write
  time -- there's no registry in the code today of which keys are expected to be
  numeric.

### Proposed spec

1. **Fix the read side, not just the write side** -- this is the part that actually
   prevents the crash for every current and future key, without needing a maintained
   list of "numeric" keys: every `float(...)`/`int(...)` parse of a Setting or Override
   value (`_get_effective_setting_float`, `_get_setting_float`, `_get_setting_int`,
   `get_gst_rate_percent`, and any other call site that parses a stored value
   numerically) wraps the parse in `try/except ValueError`, raising a clear
   `HTTPException(500, f"Setting '{key}' has a non-numeric value ('{value}') and cannot
   be used here")` instead of letting a bare `ValueError` surface as an opaque,
   undiagnosable 500. This turns "the whole document silently stops computing" into "a
   clear error naming exactly which setting is broken."
2. **Guard the GST divisor** in `pricing.py:324` -- if `1 + gst_rate_percent / 100` would
   be `<= 0`, raise a clear `HTTPException(400, ...)` naming the offending rate instead
   of letting `ZeroDivisionError` (or a nonsensical negative price) through.
3. **Write-time validation for Overrides only** (narrower than Settings, since an
   Override's `master_value` field already carries the current Master Setting's value
   at override time -- if that value happens to be numeric, the new override_value
   plausibly should be too): if `master_value` parses as a float, require
   `override_value` to also parse as a float, rejecting with `422` at creation time
   otherwise. If `master_value` isn't numeric, no constraint is added (matches point 1's
   reasoning -- some Settings are legitimately text).
4. **No change to `SettingCreate`** -- Master Settings stay free-form at write time,
   same as today; point 1's read-side fix is what actually closes the crash risk for
   both Settings and Overrides.

**Acceptance criteria:** creating an Override whose `master_value` is numeric but whose
`override_value` isn't is rejected with `422` at creation time; a numeric Override/
Setting value that later can't parse (a pre-existing bad row, or one created before this
fix) produces a clear, named `HTTPException` at the moment it's used, never a bare
`ValueError` traceback; a `gst_rate_percent` of `-100` (or any value driving the pricing
divisor to zero or below) is rejected with a clear message at computation time instead
of `ZeroDivisionError`; genuinely non-numeric Settings (company details, T&C text)
remain completely unaffected.

### Open decisions — need Director input before implementation

1. **Confirm the read-side-fix-first approach** (Decision proposed above) rather than
   trying to validate every Setting/Override as numeric at write time, which isn't
   possible without a registry of which keys are expected to be numeric that doesn't
   exist today. Confirm, or specify if you'd like such a registry built (larger scope).
2. **Confirm write-time validation for Overrides scoped to "only when `master_value` is
   itself numeric"** (point 3) -- this is a heuristic, not a guarantee (a
   currently-non-numeric Setting could later legitimately become numeric, or vice
   versa). Confirm this is acceptable, or specify a different rule.

---

## Approval

Amendment 22 (Master Settings/Override value validation): ☑ Approved — "approve as
proposed, all decisions" (19 September 2026)

Decision 1 (read-side fix first, no write-time registry): ☑ Resolved as proposed.
Decision 2 (Override write-time validation scoped to numeric `master_value`): ☑
Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
