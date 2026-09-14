# Section 6 (Phase 2) — Draft Specification for Director Approval

**Date: 14 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Continues [Section-6-specs.md](Section-6-specs.md), which shipped Phase 1 (Custom Notes
+ the `SelectWithOther` "Others" rule, scoped to Cost Sheet Builder) and explicitly
deferred Phase 2.

---

## Amendment No. 5 — Customizable Forms (Phase 2)

**Registered scope (Annexure 2, §2):** "Every dropdown gets a 'None' option; admin sets
each field compulsory/optional/hidden from Master Settings. Phase 2: field-settings
panel."

### Current state
Re-checked directly against today's code (14 Sept), since Sections 7-8 added more
screens since Phase 1's own inventory:

- **No field-settings mechanism exists anywhere.** A repo-wide search for
  compulsory/required-field/hidden-field/field-config concepts turns up nothing except
  unrelated derived business flags (e.g. `soil_test_required` — a computed flag, not an
  admin setting) and the two Annexure spec docs themselves.
- **`SelectWithOther` (Phase 1) has grown by one file** since it shipped — `RateSheet.jsx`
  now uses it for Category/Vendor — but Sections 7 and 8's new screens
  (`CrossSellAdmin.jsx`, `MessagesPanel.jsx`, `MasterSettings.jsx`'s template form) all
  added plain, un-wrapped `<select>` dropdowns instead, so the gap is not shrinking on its
  own. `SelectWithOther` has no "None" concept today either — its empty option is either a
  disabled "Select…" placeholder (when required) or an incidental empty value, not a real,
  selectable "reset to nothing."
- **New Project Setup (Detailed mode) is where "compulsory/optional/hidden" actually
  matters.** Amendment 2 already made a fixed, code-level call about which fields to keep
  ("5 required fields... soil type, distance, court count, site access, power/water
  removed → T&C") — Phase 2 is what turns that one-time decision into something the
  Director can actually change without a code deploy. Today those fields
  (`soil_condition`, `site_access`, `power_available`, `building_status`, plus
  `distance_km`, `number_of_courts`, `safe_bearing_capacity`) are **hard-required at the
  backend** (`ProjectCreate`'s Pydantic schema — non-nullable, no default) as well as the
  frontend, so "optional" isn't just a UI nicety here: the API itself 422s without them
  today.

### Proposed spec

**1. A new `FieldSetting` table** (Director-managed via a new Master Settings card,
mirroring the existing generic `Setting` table's own governance pattern — versioned,
`changed_by`/reason recorded via the audit log): `field_key` (e.g.
`project.soil_condition`), `state` (`compulsory` | `optional` | `hidden`), defaulting
every field this wave governs to `compulsory` — i.e. today's actual behavior, unchanged
until a Director deliberately opts one down.

**2. Where it applies this wave — New Project Setup's Detailed-mode fields only**, not
every dropdown in the app (same proportionality call Phase 1's own spec made for the
Others rule): `soil_condition`, `site_access`, `power_available`, `building_status`,
`distance_km`, `number_of_courts`, `safe_bearing_capacity`. `city` and the
sport/client-identity fields stay hard-required always — a project genuinely can't exist
without them, no field-setting makes that optional.

**3. What each state does:**
- **Compulsory** — today's behavior: shown, required, both frontend and backend reject a
  missing value.
- **Optional** — shown, but a real "None" option becomes selectable (dropdown fields) or
  the input can be left blank (numeric fields); backend schema accepts null for that
  field specifically.
- **Hidden** — the field doesn't render on New Project Setup at all and is never
  collected; stored as null. (A hidden field can still be filled in later from the
  project's own detail screen if genuinely needed — this only controls the *intake* form,
  not whether the column can ever hold a value.)

**4. "None" is tied to a field actually being Optional**, not sprinkled onto all ~93
dropdowns in the app regardless of whether "nothing" is a sane answer — the same
reasoning Phase 1 already applied to scope the Others rule down from "every dropdown."
Most of the app's other dropdowns (client type, package, building status *elsewhere*,
etc.) are business-logic enums that drive pricing/scope and must always carry a real
value; a blanket None would let them silently break, exactly what Phase 1's spec already
flagged as the reason not to do this indiscriminately.

**5. Enforcement stays server-side**, matching every other rule in this app:
`ProjectCreate`'s schema changes to `Type | None = None` for the seven governed fields,
and the create-project endpoint checks each one against its current `FieldSetting` state
(`compulsory` + null → 422; anything else → accepted) — a Sales user bypassing the
frontend can't submit past a field the Director actually requires, and a field the
Director hides can't be forced through either.

**Acceptance criteria:** a Director can open the new Master Settings card, set e.g. "Site
access" to Optional and "Safe bearing capacity" to Hidden; New Project Setup
immediately reflects both changes (a real "None" appears for Site access, Safe bearing
capacity disappears from the form entirely); a project can now be created without either
value; setting a field back to Compulsory restores today's exact behavior, including the
backend 422 on a missing value.

### One open decision — needs Director input before implementation

**Decision A — how far does Phase 2 reach this wave?**
- **New Project Setup's 7 fields only (Recommended):** the concrete, already-registered-
  adjacent scope above — turns Amendment 2's one-time hardcoded decision into a real,
  Director-changeable setting. Smaller, ships this wave.
- **Every dropdown/required field across the whole app (~93 sites, 15+ files):** the
  literal "every dropdown" reading — RateSheet's own required fields, Cost Sheet
  Builder's remaining raw selects, Estimate/Quotation creation, etc. all get the same
  treatment too. Substantially larger build; every one of those ~93 sites would need
  auditing individually for whether "optional"/"hidden" even makes sense for it (most
  don't — e.g. a Rate Item's own category isn't optional).

---

## Approval

Amendment 5 Phase 2: ☐ Approved ☐ Changes ☐ Later
Decision A (scope): ☐ New Project Setup only ☐ Every dropdown/required field app-wide

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 14 September 2026
