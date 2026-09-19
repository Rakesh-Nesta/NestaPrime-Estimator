# Section 27 — Draft Specifications for Director Approval

**Date: 19 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same second proactive gap audit as Sections 25-26,
spot-verified against the live code before being registered as Amendment No. 21.

---

## Amendment No. 21 — No Double-Submit Guard on Cost Sheet Take-Off Forms

**Registered scope (Annexure 2, §Amendment 21):** none of the 21 take-off entry forms in
`CostSheetBuilder.jsx` guard against a double-click submitting the same line twice.

### Current state (verified by direct grep and read)

`frontend/src/CostSheetBuilder.jsx` contains 21 separate `async function submit`
handlers (Structure, Manual Line, Flooring, Lighting, HVAC, Athletics, and every other
per-category take-off form), confirmed by `grep -c "async function submit"`. None of
them track a `saving`/`submitting` flag or disable their submit button during the
`await` -- confirmed by grepping the file for `isSubmitting`/`setSubmitting`/
`disabled={saving`, all zero matches in this file for these per-category forms (a
narrower, unrelated `saving` state does exist at line 252/340, for a different action).
This app already has an established, working pattern for exactly this elsewhere --
`ClientsAdmin.jsx`, `CrossSellAdmin.jsx`, `ClientSignatoriesPanel.jsx`,
`CoverNotePanel.jsx`, `App.jsx`, and others all use a local
`const [saving, setSaving] = useState(false)`, set `true` before the request and reset
in a `finally`, with the submit button's `disabled` prop reading that state. Its absence
here is inconsistent with the codebase's own convention, not a deliberate omission.
Double-clicking any of these forms' submit button fires two identical POSTs before the
first resolves, silently duplicating a cost-sheet line and inflating `cost_total` --
real financial impact on the screen this app's own pricing accuracy depends on most.

### Proposed spec

1. **Apply the codebase's own existing pattern to all 21 submit handlers**: each
   per-category form component gains a local `const [saving, setSaving] = useState(false)`;
   its `submit` function sets `saving(true)` immediately after `e.preventDefault()`,
   wraps the existing try/catch's body unchanged, and resets `saving(false)` in a
   `finally` (so it clears on both success and failure, matching the existing pattern
   used elsewhere). The submit `<button>` gets `disabled={saving}` added to whatever
   condition it already has (several already disable on other conditions, e.g. a
   required field being empty -- this is additive, not a replacement).
2. **No shared abstraction/hook introduced** -- 21 independent local `useState` calls,
   matching how every other guarded form in this codebase already does it, rather than
   inventing a new shared pattern for this one file.
3. **No backend change** -- purely a frontend guard against a client-side double-fire;
   the backend has no way to distinguish a legitimate second identical line from a
   double-submit, so this is the correct layer to fix it at.
4. **No visual/copy change beyond the guard itself** -- buttons already showing their
   own label (e.g. "Compute & add to Cost Sheet") stay as-is; this spec doesn't propose
   a "Saving..." label change unless the Director wants one (see Open Decisions).

**Acceptance criteria:** rapidly double-clicking any of the 21 take-off forms' submit
button results in exactly one POST and one cost-sheet line, not two; the button
re-enables automatically after the request resolves (success or failure); existing
per-form disable conditions (e.g. required-field checks) continue to work unchanged.

### Open decisions — need Director input before implementation

1. **Confirm applying the guard to all 21 forms uniformly**, rather than a subset --
   proposed as the full fix, since every one of the 21 forms shares the identical
   underlying risk (an unguarded async submit).
2. **Should the button's label change while saving** (e.g. to "Saving..." or "Adding..."),
   matching what some of the other already-guarded forms in this app do, or is the
   `disabled` state alone sufficient feedback? Proposed: label change is a nice-to-have,
   not required for this fix -- ship the guard first, revisit copy separately if wanted.

---

## Approval

Amendment 21 (double-submit guard on Cost Sheet take-off forms): ☑ Approved — "approve
as proposed, all decisions" (19 September 2026)

Decision 1 (apply to all 21 forms uniformly): ☑ Resolved as proposed.
Decision 2 (button label change while saving, not required for this fix): ☑ Resolved
as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 19 September 2026
