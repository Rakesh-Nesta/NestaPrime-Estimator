# Section 30 — Draft Specifications for Director Approval

**Date: 20 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a fourth Director-requested proactive gap audit
against the register, spot-verified against the live code before being registered as
Amendment No. 24.

---

## Amendment No. 24 — Quotation PDF and Billing Handoff Hardcode a False "18% Flat" GST Label

**Registered scope (Annexure 2, §Amendment 24):** the client-facing Quotation PDF and
the internal Billing Handoff export both print a literal "18% (flat)" GST label next to
the real, computed GST amount, regardless of what rate was actually applied.

### Current state (verified against `backend/app/api/pdf_documents.py:841` and
`backend/app/api/exports.py:288`, direct read)

```python
# pdf_documents.py:841
["GST @ 18% (flat)", format_inr(gst_amount)],

# exports.py:288
("Total (GST-inclusive, 18% flat)", float(quotation.quotation_total)),
```

Neither label is derived from the actual rate -- both are plain string literals. The
`Quotation` model (`backend/app/models/document.py:361-372`) stores `gst_amount` and
`selling_after_discount` but no `gst_rate_percent` column; the effective rate that
produced `gst_amount` can be reliably back-derived as
`gst_amount / selling_after_discount * 100`, which holds in both `GstMode.EXCLUSIVE`
and `GstMode.INCLUSIVE` (in both, `selling_after_discount` is the ex-GST base --
confirmed against `pricing.py`'s own `compute_pricing`). That rate is Director-
configurable and, per Note R1's own shipped work, blends in a 5% rate for HSN-9506
sports-equipment lines when a Cost Sheet mixes equipment with 18%-rated civil/flooring
work (`cost_weighted_gst_rate_percent`, `pricing.py:256-274`) -- so a real quotation can
easily carry an effective rate that isn't literally 18%.

### Proposed spec

1. **Back-derive the displayed rate from the document's own stored, frozen values** --
   `gst_amount / selling_after_discount * 100` (guarding `selling_after_discount == 0`,
   falling back to the label's current wording in that edge case) -- rather than
   re-querying `get_gst_rate_percent(db)`/current Master Settings. This is the only
   internally-consistent choice: the rupee `gst_amount` already printed on the document
   was computed from the rate *as it stood when the quotation was created/last revised*,
   not whatever the Setting happens to be today. Re-deriving from current settings could
   print a rate that doesn't match the rupee amount sitting right next to it.
2. **`pdf_documents.py:841`** becomes `[f"GST @ {rate:.1f}%", format_inr(gst_amount)]`
   where `rate = (gst_amount / selling_after_discount * 100) if selling_after_discount
   else 18.0`.
3. **`exports.py:288`** becomes `(f"Total (GST-inclusive, {rate:.1f}%)",
   float(quotation.quotation_total))`, same derivation.
4. **Drop the word "(flat)"/"flat"** from both labels -- a cost-weighted blended rate
   across multiple sports/HSN codes is no longer a single uniform per-line rate, so
   claiming "flat" is its own small inaccuracy once the rate becomes dynamic. Replace
   with just the computed percentage.
5. **No change to the underlying `gst_amount`/`quotation_total` figures themselves** --
   this is a label-only fix; the amounts were always computed correctly, only the text
   describing them was wrong.

**Acceptance criteria:** a Quotation whose effective GST rate is not exactly 18% (e.g.
a Cost Sheet mixing HSN-9506 equipment at 5% with civil work at 18%) shows the correct
blended percentage on both the Quotation PDF and the Billing Handoff export, matching
the rate implied by the already-printed rupee `gst_amount`; a Quotation whose effective
rate genuinely is 18% continues to show "18.0%"; no change to any numeric total.

### Open decisions — need Director input before implementation

1. **Confirm back-deriving the rate from the document's own stored `gst_amount`/
   `selling_after_discount`** (proposed, the only internally-consistent option) rather
   than looking up the current Master Setting, which could disagree with the rupee
   amount already printed.
2. **Confirm dropping "(flat)"/"flat" from both labels.** Alternative: keep "(flat)"
   only when the derived rate happens to equal a single configured flat rate, and use
   different wording (e.g. "blended") when it doesn't -- more precise, but adds a
   branch for a cosmetic distinction. Proposed: drop it unconditionally, simpler and
   still accurate.

---

## Approval

Amendment 24 (dynamic GST label): ☑ Approved — "approve as proposed, all decisions"
(20 September 2026)

Decision 1 (back-derive from stored values, not current settings): ☑ Resolved as
proposed.
Decision 2 (drop "(flat)"/"flat" unconditionally): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 20 September 2026
