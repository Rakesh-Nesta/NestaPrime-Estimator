# Section 46 — Spec Doc

## Amendment No. 40 — No "What's Next" Guidance for Sales Across the Document Stages

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 40. This is the
direct fix for the bottleneck the Director named as the app's central problem: *"my hole
point round to sales persons or his actual bottle neck."*

### Current state

`frontend/src/Documents.jsx`'s stage headers (`:384` Cost Sheet, `:600` Estimate,
`:1068` Quotation, `:1434` Work Order) show only a status badge/SLA note, never a
next-step or whose-turn hint. Confirmed by whole-file grep for
"your turn"/"whose turn"/"what's next"/"next step"/"awaiting sales/pm/director" -- zero
matches. Real status values available to compute a hint from
(`backend/app/models/document.py`): `CostSheetStatus` (DRAFT/VERIFIED/SUPERSEDED/
UNVERIFIED), `EstimateStatus` (DRAFT/SENT/EXPIRED, plus a derived client-approval status
per option), `QuotationStatus` (DRAFT/RELEASED/SENT/WON/LOST/EXPIRED).

### Proposed spec

1. A single small status-hint line under each stage's existing header, computed
   client-side from the stage's own already-loaded status -- no new backend endpoint,
   no new field, purely a read of data Documents.jsx already has.
2. Visible to **every role**, not gated to Sales only -- simpler, more consistent, and a
   PM/Director benefits from the same at-a-glance state just as much.
3. Indicative copy per stage (exact wording confirmed during implementation against a
   live preview, not locked here -- see Open Decision 1):
   - **Cost Sheet:** none yet -> "Awaiting PM/Director to build the Cost Sheet"; Draft/
     Unverified -> "Awaiting PM/Director to verify"; Verified -> "Ready -- an Estimate
     can now be created."
   - **Estimate:** none yet (Cost Sheet Verified) -> "Awaiting PM/Director to create the
     Estimate"; Draft -> "Awaiting send to client"; Sent -> "Awaiting client response";
     a client-approved option exists -> "Client approved -- a Quotation can now be
     created."
   - **Quotation:** none yet (an Estimate option approved/demanded) -> "Awaiting PM/
     Director to create the Quotation"; Draft -> "Awaiting release"; Released -> "Ready
     to send to client"; Sent -> "Awaiting client decision"; Won -> "Won -- Work Order
     can be created"; Lost -> "Lost -- a new Quotation can be raised to re-bid."
4. No change to any status transition, role gate, or backend logic -- purely an
   additional line of computed, read-only text.

**Acceptance criteria:**
- Every stage that has reached at least one document (Cost Sheet created, etc.) shows a
  plain-language hint matching its current real status.
- A stage with no document yet shows a hint explaining what's being waited on before it
  can start.
- The hint text never contradicts the status badge already shown next to it.
- Visible to all roles, including Sales.

### Open decisions

1. **Exact copy per status** -- the strings above are indicative, not final. Proposed
   default: implement with this indicative copy, Director reviews against a live
   preview before merge, same as Amendment 14's company-details editor got a live
   preview before its own copy was finalized.
2. **Placement: directly under each stage header (proposed default) vs. a single
   consolidated "what's next" summary at the top of the whole Documents screen?**
   Proposed default: **per-stage**, directly under each header -- keeps the hint next to
   the status it explains, and this screen already has four separate stage sections a
   single summary would have to compress.

## Approval

☐ Approved — pending Director decision.

---
Prepared by: R. Patni (with AI development assistance) | Date: 22 September 2026
