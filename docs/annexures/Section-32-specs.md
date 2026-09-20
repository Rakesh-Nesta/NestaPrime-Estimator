# Section 32 — Draft Specifications for Director Approval

**Date: 20 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a fifth Director-requested proactive gap audit
against the register, spot-verified against the live code before being registered as
Amendment No. 26.

---

## Amendment No. 26 — Re-Creating an Estimate or Quotation for a Project Crashes (500)

**Registered scope (Annexure 2, §Amendment 26):** `create_estimate`/`create_quotation`
always hardcode `document_no` revision `1`, with no check for an existing document on
the project -- a second call collides against the `unique=True` constraint and crashes.

### Current state (verified against `backend/app/api/documents.py`, direct read)

`create_estimate` (lines 1405-1452) and `create_quotation` (two creation paths, lines
1943 and 2114) all call `_document_no(project.project_no, "EST"/"NPQ", 1)` with the
revision hardcoded to `1`, and neither queries for an existing Estimate/Quotation on the
project first. The "revise" endpoints (`revise_estimate` line 1652,
`revise_quotation`-equivalent line 2305) correctly increment `old.revision_major + 1`,
but both require the document being revised to still be in `SENT` status
(`revise_estimate`: `if old.status != EstimateStatus.SENT: raise ... 400`) -- **not
viable** for a project whose Estimate/Quotation has already moved past that (e.g. the
Quotation reached `LOST`), which is exactly the scenario that needs a fresh document
chain (re-bidding a lost pursuit). Today, that scenario has no working path at all: the
"start fresh" endpoint crashes, and the "revise" endpoint refuses.

### Proposed spec

1. **`create_estimate`/`create_quotation` compute the next `revision_major` from what
   already exists on the project**, rather than hardcoding `1`: query the highest
   existing `revision_major` among Estimates (or Quotations) for this `project_id` and
   use `max_existing + 1` (or `1` if none exist yet). This mirrors the same
   "read-existing-then-compute-next" shape Amendment 23 already uses for
   `_generate_project_no`/`_po_number`, reused here for consistency rather than
   inventing a new pattern -- and, unlike those two, there's no concurrency concern to
   retry against, since a project only gets a second Estimate/Quotation through a
   deliberate, infrequent PM/Director action, not a high-frequency creation path.
2. **No change to the "revise" endpoints or their `SENT`-only precondition** -- revising
   an in-flight document and starting an entirely new document chain after a project's
   pursuit concluded (Won/Lost) are two different, already-distinct actions in this
   codebase; this fix only makes the second one actually work.
3. **No schema change** -- `revision_major` already exists on both `Estimate` and
   `Quotation`; this only changes how its *initial* value is computed on the "create
   fresh" path.

**Acceptance criteria:** creating a second Estimate for a project whose first Estimate's
Quotation reached `WON` or `LOST` succeeds, with a `document_no` distinct from the
first (e.g. `EST-{suffix}-R2` if the project's highest existing Estimate revision was
1); the identical behavior for `create_quotation`; a project's very first Estimate/
Quotation still gets `R1` exactly as today; no change to any other document-numbering
behavior.

### Open decisions — need Director input before implementation

1. **Confirm "compute next revision from existing rows" (proposed above) as the fix**,
   rather than blocking a second Estimate/Quotation entirely and requiring some other
   workflow to restart a project's pursuit. Given the "revise" path is confirmed
   unusable for this scenario (it requires `SENT` status), proposed is the only option
   that actually unblocks re-bidding a lost project without a larger redesign.
2. **Should a genuinely fresh Estimate/Quotation for a project with a prior Lost
   pursuit visually/semantically read as "R2" (implying it's a revision of the same
   pursuit), or should it get some other marker distinguishing it as a new pursuit
   attempt** (e.g. a different prefix or a gap in numbering)? Proposed: keep `R2`/`R3`
   etc. as-is -- simplest, no schema change, and the underlying `Quotation`/`Estimate`
   rows already carry their own distinct `status` history showing the prior one was
   Lost, so the numbering alone isn't the only record of what happened.

---

## Approval

Amendment 26 (fix re-creation crash): ☑ Approved — "approve as proposed, all decisions"
(20 September 2026)

Decision 1 (compute next revision from existing rows): ☑ Resolved as proposed.
Decision 2 (R2/R3 numbering for a fresh pursuit, no separate marker): ☑ Resolved as
proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 20 September 2026
