# Section 22 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Amendment 5's two remaining gaps (field-settings governance scoped to 5
fields; the "Others" dropdown rule wired into only 2 dropdowns), re-verified 19
September and confirmed still real, unlike several other entries corrected this week.
This spec proposes a bounded next increment for each rather than the literal "every
field" / "every dropdown" reading — the same proportionality call Amendment 5's own
prior phases already made.

---

## Amendment No. 5, continued (Part A) — Field-Settings: Add `water_available`

### Current state

`GOVERNED_FIELD_KEYS` (`backend/app/api/field_settings.py`) covers `soil_type`,
`distance_km`, `number_of_courts`, `site_access`, `power_available` — five fields.
`field_setting.py`'s own docstring explains three deliberate exclusions:
`building_status` (said to be one of Amendment 2's "kept 5" required fields — this
citation is actually imprecise, Amendment 2's fifth field is `project_type`/"Base
scope-status", not `building_status`, though `building_status` has its own genuine
reason to stay excluded: it's `nullable=False` at the DB level and D.4's
`soil_test_required`/clear-height logic branches directly on it); `water_available`
("boolean, doesn't fit the None-option model"); `site_condition` ("never named as a
T&C candidate," which the docstring itself concedes is not a technical reason).

Amendment 2's own spec text names fields to remove from the required set: *"soil type,
distance, court count, site access, power/water removed (→ T&C)"* — `water_available`
is `power_available`'s explicitly named pair, and it's the one that didn't make it into
governance. Checked for a real downstream blocker: `water_available` isn't read by any
derived logic (`dewatering_required` comes from `site_condition == WATER_LOGGED`, not
from `water_available`) — the stated exclusion is a UI-shape mismatch (today it's a
plain checkbox, and "Optional" needs a real selectable "None," which a two-state
checkbox can't offer), not a technical blocker.

**Noted, not actioned:** an old, unapproved draft (`Section-6-phase2-specs.md`, 14
September, Decision A checkboxes still blank) proposed a *different* 7-field set
including `building_status` and `safe_bearing_capacity`. That draft is now in tension
with the reasoning `field_setting.py` actually shipped with (which argues
`building_status` should stay excluded). Flagging this contradiction for the record
rather than silently resolving it — recommend treating that older draft as superseded/
informational only; it was never approved and the two other fields it proposed
(`building_status`, `safe_bearing_capacity`) aren't part of this spec.

### Proposed spec

1. **`Project.water_available` becomes nullable** (`bool | None`, new Alembic
   migration) — the same "Optional → null accepted" shape every other governed field
   already has. `ProjectCreate.water_available: bool | None = None`.
2. **Frontend: replace the plain checkbox with a `<Select>`**, matching
   `power_available`'s exact existing pattern (`fieldState("water_available") !==
   "hidden"`, `placeholder={... === "optional" ? "None" : undefined}`) — Yes/No options,
   gated the same way.
3. **Add `water_available` to `GOVERNED_FIELD_KEYS`** and to `MasterSettings.jsx`'s
   `FIELD_LABELS` ("Water available") — the Director's existing Field Settings card
   picks it up automatically, no new admin UI needed.
4. **Backend compulsory-check** (`backend/app/api/projects.py`'s create-project
   validation loop) gains `water_available` alongside the existing three Select-backed
   fields it already checks.

**Acceptance criteria:** the Director can set "Water available" to Optional in the
existing Field Settings card; New Project Setup then shows a real "None" choice for it;
a project can be created without a value; setting it back to Compulsory restores
today's exact required-checkbox behavior including the backend 422 on a missing value.

---

## Amendment No. 5, continued (Part B) — Wire City/District into the Others Rule

### Current state

`ProjectSetup.jsx`'s `CITIES` array ends in a plain `"Other"` string, rendered through
the generic `Select` component on both Quick and Detailed mode (lines 363, 471) — not
`SelectWithOther`. Selecting "Other" submits the literal string `"Other"` as the
project's city; nothing reveals a text input, and the backend (`city: str`, no
validation) can't tell a real client site named "Other" from the placeholder. It's
fully inert today, not partially wired.

Checked the rest of the app for other good candidates (per `SelectWithOther.jsx`'s own
scoping comment: client-facing labels, not business-logic enums that drive computed
pricing/scope) — City is the clean, obvious next one: small curated list, a real
"client site isn't in our list" scenario, already has a half-built placeholder, and
needs no backend schema change since `city` is already a plain string. Everything else
checked (client type, package, labour category, engineering parameters like structure/
soil/seismic types, message channel, user role, vendor/rate-item pickers) is either
already free text, already data-driven from a live catalog, or a real business-logic
enum other code depends on — excluded for the same reason Amendment 5's prior phases
already excluded those categories.

### Proposed spec

1. **Replace `CITIES` + plain `Select` with `SelectWithOther`** on both Quick and
   Detailed mode's City field (`options={CITIES.filter((c) => c !== "Other")}`, drop
   the now-redundant static `"Other"` entry since `SelectWithOther` supplies its own
   "Others…" option, `required`).
2. **No backend change** — `city` is already an unvalidated plain string; a typed
   city name behaves exactly like a picked one.

**Acceptance criteria:** picking a listed city behaves exactly as today; picking
"Others…" reveals a text input, and the typed value becomes the real `city` value sent
to the backend (not the literal string `"Others…"`); a project whose city was already
set to a value outside `CITIES` (there shouldn't be any today, since it was previously
impossible, but the component's own existing "unrecognized value starts in Others mode"
behavior covers it for free) displays correctly.

### Open decisions — need Director input before implementation

1. **Confirm both parts ship together in one PR** (proposed, since they're both small,
   independent, previously-scoped-and-then-deferred Amendment 5 slices) vs. splitting
   into two.
2. **Confirm the `Section-6-phase2-specs.md` draft is treated as superseded**
   (proposed) — its `building_status`/`safe_bearing_capacity` proposal is not part of
   this spec and isn't being actioned now.

---

## Approval

Amendment 5 continuation (add `water_available` to field-settings governance; wire
City/District into the Others rule): ☐ Pending Director approval.

Decision 1 (both parts ship in one PR): ☐ Pending.
Decision 2 (Section-6-phase2-specs.md treated as superseded): ☐ Pending.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
