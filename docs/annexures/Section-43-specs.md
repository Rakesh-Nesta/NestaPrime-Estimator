# Section 43 — Spec Doc

## Amendment No. 37 — Existing-Client Selection Never Auto-Fills City

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 37.

### Current state

`frontend/src/ProjectSetup.jsx:64` hardcodes `city: "Mumbai"` in `emptyForm`. The effect
that fires on existing-client selection (`ProjectSetup.jsx:137-141`) auto-fills `package`
and `paymentTerms` only. `backend/app/models/client.py` has no structured `city` column,
only free-text `billing_address` (line 36).

### Proposed spec

1. Add a nullable `city: Mapped[str | None]` column to `Client` (migration).
2. `ClientOut`/`ClientCreate`/`ClientUpdate` schemas (`backend/app/api/clients.py`) gain
   `city`.
3. `ClientsAdmin.jsx`'s client create/edit form gains a plain City text input, same style
   as its existing fields -- optional, no validation beyond normal string length.
4. `ProjectSetup.jsx`'s existing-client-selection effect (the same one already filling
   `package`/`paymentTerms`) also sets `form.city` from the selected client's `city`,
   **only when that client has one set** -- an existing client with no city on record
   leaves the field as whatever the user already had (does not force it back to
   "Mumbai" or blank).
5. **No automated backfill** from `billing_address` -- free-text address parsing risks
   silently assigning a wrong city to a real client. Existing clients simply have
   `city: null` until a Director/PM fills it in from Client Admin.

**Acceptance criteria:**
- Selecting an existing client with a city on record fills the Project Setup city field
  with it.
- Selecting an existing client with no city on record does not overwrite whatever the
  user had already typed.
- New clients can have a city set at creation; existing clients can have one added via
  Client Admin.
- No project's `city` is silently changed by this amendment -- it only affects what the
  form pre-fills with, same as `package`/`paymentTerms` already do.

### Open decisions

1. **Should `city` be required on new clients going forward, or stay optional
   indefinitely?** Proposed default: **optional** -- many real clients (individuals,
   smaller schools) may not have had it collected, and this amendment's job is to stop
   defaulting to the wrong city, not to force new data-entry burden retroactively.
2. **Should Client Admin's list view show city as a column?** Proposed default: **not in
   this amendment** -- out of scope; the ask was specifically about the auto-fill gap,
   not a Client Admin redesign.

## Approval

☑ Approved — "approve as proposed, all decisions" (22 September 2026).

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
