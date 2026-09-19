# Section 25 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a second Director-requested proactive gap audit
against the register, spot-verified against the live code before being registered as
Amendment No. 19.

---

## Amendment No. 19 — Structure Form Crash on an Unrecognized Recommendation

**Registered scope (Annexure 2, §Amendment 19):** the Structure take-off form's "Use
recommendation" button can crash the whole form with an uncaught `TypeError` instead of
either working correctly or being disabled.

### Current state (verified against `frontend/src/CostSheetBuilder.jsx`, direct read)

```js
const recStructureType = rec && mapStructureType(rec.structure_type);   // line 407
const recIsVendorQuoteOnly = recStructureType && ["e", "f"].includes(recStructureType.type);  // 410

function useRecommendation() {                                          // 412-420
  setF((s) => ({
    ...s,
    structure_type: recStructureType.type,   // <- crashes if recStructureType is null
    ...
  }));
}
...
<RecommendationBanner
  onUse={!recIsVendorQuoteOnly ? useRecommendation : undefined}         // 462
  note={recIsVendorQuoteOnly ? "..." : !recSection ? "section not recognised..." : undefined}
/>
```

When E.4's recommended `structure_type` doesn't match `mapStructureType`'s known values,
`recStructureType` is `null`. `recIsVendorQuoteOnly` (`recStructureType && [...]`) is then
also `null` (falsy) -- not `true`, not `false`, just falsy for the wrong reason. `!null`
evaluates `true`, so `onUse` still gets wired to `useRecommendation`, and the banner shows
no warning (the `note` ternary only covers `recIsVendorQuoteOnly` and `!recSection`, never
`!recStructureType`). Clicking the button then reads `recStructureType.type` on `null`,
throwing `TypeError: Cannot read properties of null (reading 'type')` -- confirmed by
direct trace, not assumed. The sibling `BaseForm` (line 579, same file) avoids this
exact bug by gating its own "Use recommendation" button directly on `recBaseType` itself,
not on a derived flag that can independently go falsy for an unrelated reason.

### Proposed spec

1. **Fix the `onUse` gate** to check `recStructureType` directly:
   `onUse={recStructureType && !recIsVendorQuoteOnly ? useRecommendation : undefined}` --
   matching `BaseForm`'s already-correct pattern.
2. **Add the missing "not recognised" note**, so the banner explains itself instead of
   silently disabling: extend the `note` ternary to cover `!recStructureType` (e.g. "type
   not recognised -- pick manually"), alongside the existing `!recSection` case.
3. **Defensive guard inside `useRecommendation()` itself** as a second layer, not just
   relying on the button being correctly disabled: `if (!recStructureType) return;` at
   the top of the function -- cheap insurance against the same class of bug recurring if
   the gating condition is ever touched again without this function being re-checked.
4. **No backend change** -- this is a pure frontend fix, one file.

**Acceptance criteria:** when a recommended structure type doesn't parse, the "Use
recommendation" button either doesn't render as clickable or is accompanied by a clear
"type not recognised -- pick manually" message; clicking it in that state never throws;
the existing, already-working "vendor-quote type" and "section not recognised" cases are
unaffected.

### Open decisions — need Director input before implementation

1. **Confirm the three-part fix above** (button gate, added note, defensive guard) is
   the right scope -- proposed as the minimal correct fix, matching the existing
   `BaseForm` pattern rather than inventing a new one.
2. **Exact wording for the new "type not recognised" note** -- proposed: "type not
   recognised -- pick manually", mirroring the existing "section not recognised -- pick
   manually" phrasing exactly. Confirm or supply alternate wording.

---

## Approval

Amendment 19 (Structure form crash fix): ☑ Approved — "approve as proposed, all
decisions" (19 September 2026)

Decision 1 (three-part fix scope): ☑ Resolved as proposed.
Decision 2 (note wording, "type not recognised -- pick manually"): ☑ Resolved as
proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
