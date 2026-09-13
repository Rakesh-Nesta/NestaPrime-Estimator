# Section 6 — Draft Specifications for Director Approval

**Date: 13 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: Annexure 2's own priority sequencing pairs "No. 5 (customizable fields) +
No. 7 (vendor master)" as Section 6 — "flexibility + procurement bridge."

---

## Amendment No. 5 — Customizable Forms

**Registered scope (Annexure 2, §2):** "Every dropdown gets a 'None' option; admin sets
each field compulsory/optional/hidden from Master Settings. Phase 1: None options +
dashboard. Phase 2: field-settings panel." Plus, merged in 12 Sept: the dropdown
"Others" rule (typed text becomes the Cost Sheet/Quotation display label) and a Custom
Notes component (Project Setup, Cost Sheet, Estimate screens; passed through to the
Quotation PDF under "Special Remarks / T&C").

### Current state
A full inventory finds roughly **93 dropdown instances across 15 files** — and critically,
**no shared Select/Dropdown component exists anywhere in the app**. Three files each
independently hand-rolled their own local wrapper (`Select` in `ProjectSetup.jsx`,
`LabeledSelect` in `SportsScopeAdmin.jsx`, `SelectInput` in `CostSheetBuilder.jsx`,
accounting for 35 + 17 + 7 of the 93), and the rest are raw, unwrapped `<select>` tags
scattered across `Documents.jsx`, `MasterSettings.jsx`, `PriceRequests.jsx`,
`RateSheet.jsx`, and eight more files. "Append Others / add None to every dropdown" and
"admin sets each field compulsory/optional/hidden" cannot be done centrally today —
every one of those ~93 sites (or the handful of patterns behind them) would need
touching individually.

`Project` has no free-text notes/remarks column at all — Custom Notes needs a new
column and migration; there's nothing to repurpose. `pdf_documents.py` already
assembles a "Special Remarks / T&C" block on the Quotation PDF (currently populated
from blueprint-derived static/derived text, e.g. Quick-mode's blind-quoting
assumptions) — a real, existing insertion point Custom Notes can append into.

### Proposed spec — phased, matching the amendment's own "Phase 1 / Phase 2" language

**This wave (Phase 1):**

1. **Custom Notes component.** A new `Project.custom_notes` text column (nullable). A
   reusable `+ Add Note` button on Project Setup, Cost Sheet Builder, and the Estimate
   screen — toggles a multi-line textarea, saves to the same project-level field
   regardless of which screen it's opened from (one note per project, not one per
   screen — the registered text describes it as "persisted on the Project record,"
   singular). Appended into the existing Quotation PDF "Special Remarks / T&C" block
   when non-empty.
2. **Dropdown "Others" rule — scoped, not literal "every dropdown."** Building a shared
   component and retrofitting 93 existing sites in one wave isn't proportionate to what
   this amendment is actually trying to fix: dropdowns whose value becomes a
   *client-facing label* on a Cost Sheet or Quotation, where a real category might
   genuinely not have a matching option yet. That's a specific subset — item/category/
   spec-style dropdowns in Cost Sheet Builder's take-off tabs and Manual Line, not
   business-logic enums like site condition, soil type, or client type, which drive
   computed pricing/margin/scope logic and would silently break if freely overridden
   with arbitrary typed text. Proposed v1: a new shared `SelectWithOther` component
   (Others appends, reveals a text input, typed text becomes the effective value) wired
   into Cost Sheet Builder's category/item-name-style dropdowns only.
3. **"None" option — deferred to Phase 2**, alongside the admin compulsory/optional/
   hidden field-settings panel, exactly as the amendment's own phasing describes. Adding
   "None" everywhere without the field-settings panel to make a field genuinely optional
   has no real effect on its own; building them together in Phase 2 avoids doing the
   first half twice.

**Acceptance criteria (Phase 1):** a Custom Note typed on any of the three named
screens appears identically from the other two (same project, same field); a non-empty
note appears on the Quotation PDF's Special Remarks / T&C section; Cost Sheet Builder's
category/item dropdowns let a user select Others and type a custom label that then
displays on the Cost Sheet and downstream Quotation exactly as typed.

---

## Amendment No. 7 — Vendor & Product Master

**Registered scope (Annexure 2, §2):** "Vendor lists with vendor codes; products with
approximate pricing under each vendor; feeds rate sheet and price-update requests."

### Current state
Vendor CRUD already exists (`backend/app/api/vendors.py`, pm/director/procurement) with
a real model (name, city, category, contact, GSTIN, payment terms, reliability score,
consent flags) — but **no vendor code field exists at all**, and **there is no
standalone Vendors screen in the frontend** — a vendor can currently only be created or
picked from wherever a vendor dropdown happens to appear (Price Requests, Purchase
Orders), never browsed or edited as its own list. **No Product model exists anywhere**
— `RateItem` is a single flat, vendor-agnostic rate card (one rate per item, not "vendor
A quotes X, vendor B quotes Y" for the same product), and `RateItem.vendor` is a free
free-text string, not a link to the real Vendor table. Price requests already use a
real `vendor_id` foreign key (genuinely picked from a list, not typed) — that half of
"feeds ... price-update requests" already works; the Rate Sheet half doesn't.

### Proposed spec
1. **Vendor code.** Add `Vendor.vendor_code` (string, unique, Director/Procurement-set)
   + migration; surface in create/update/list.
2. **A real Vendors screen** (new `frontend/src/VendorsAdmin.jsx`, pm/director/
   procurement) — list, create, and edit vendors with every existing field plus the new
   code. This is the actual "Vendor... Master" the amendment names; today there is
   nowhere in the app to see the full vendor list at all.
3. **Product model** — `vendor_id` FK, product name, spec, unit, approximate price,
   category, optional notes. CRUD nested under each vendor on the same screen (expand a
   vendor to see/add its products) — "products... under each vendor," matching the
   registered wording exactly.
4. **Rate Sheet's vendor field becomes a real picker.** `RateSheet.jsx`'s "Vendor" input
   is currently plain free text; convert it to a dropdown sourced from the real Vendor
   list (with the Others-typed-text fallback from Amendment 5's rule 2 above, in case a
   vendor genuinely isn't in the master yet) — this is the actual mechanism by which
   Amendment 7 "feeds rate sheet."
5. **Price-update requests** already reference real vendors; linking a Product's
   approximate price into a price-request line as a suggested starting figure is a
   reasonable stretch goal but not required to satisfy the registered text, which only
   asks that the master data "feeds" that flow, not that it auto-populates it —
   proposed as out of scope for this wave, flagged for a later pass if useful in
   practice.

**Acceptance criteria:** a PM/Director/Procurement user can open a Vendors screen,
create a vendor with a code, add one or more products with approximate prices under it,
and later pick that same vendor from a real list (not free text) when entering a Rate
Sheet item.

---

## Approval

Amendment 5 (Phase 1 as scoped above): ☐ Approved ☐ Changes ☐ Later
Amendment 7: ☐ Approved ☐ Changes ☐ Later

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 13 September 2026
