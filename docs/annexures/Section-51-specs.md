# Section 51 — Amendment No. 45 Spec

## Amendment No. 45 — Leads & Clients Polish: Hide Admin-Only Flags, Add Notes Field

### Registered scope
Two small fixes to the Leads & Clients / Opportunities screens, raised together by the
Director from a direct review of the Sales-facing surface audit:
1. Hide the Overdue/Blacklisted controls from every role but Director (**already
   implemented** -- see Annexure-2's registration entry; this spec covers item 2 only).
2. Add a general Notes/Remarks field to the "Add a client" and "Add Enquiry" forms.

### Current state (file:line evidence)
- `Client` (`backend/app/models/client.py`) has no general free-text field. Its only
  note-like field, `follow_up_note` (Amendment 42, `String(200)`), is specifically tied to
  the *next follow-up reminder* and isn't part of `ClientCreate` -- only set afterward via
  `PATCH /clients/{id}/follow-up`.
- `Opportunity` (`backend/app/models/opportunity.py`) has the same gap: `follow_up_note`
  exists but is follow-up-specific, and `OpportunityCreate` (`backend/app/api/
  opportunities.py`) doesn't even accept it at creation time.
- `Project.custom_notes` (`project.py:172`, `Text`, nullable) is the established pattern
  for exactly this need -- Amendment 5's "+ Add Note," a free-text catch-all distinct from
  any structured field, already used on Project Setup/Cost Sheet/Estimate.

### Proposed spec
1. **`Client.notes`** (`Text`, nullable) -- new column, distinct from `follow_up_note`.
   Added to `ClientCreate` (optional) and `ClientOut`; settable at creation via the
   existing `POST /clients`, no new endpoint. Also editable afterward via a new
   `PATCH /clients/{id}/notes` (mirrors the narrow-endpoint convention `follow-up` and
   `consent` already use) rather than folding into `update_client_flags`, since that
   endpoint's role gate is Director-only and notes should stay Sales/PM/Director like
   client creation itself.
2. **`Opportunity.notes`** (`Text`, nullable) -- same shape, distinct from `follow_up_note`
   and `lost_reason`. Added to `OpportunityCreate` (optional) and `OpportunityOut`. Editable
   afterward via a new `PATCH /opportunities/{id}/notes` (same role gate as the other
   Opportunity write endpoints: sales/pm/director).
3. **UI**: a `<textarea>` (multi-line, visually distinct from the existing single-line
   inputs -- matching the Director's "one long box" ask), labeled "Notes / remarks," added
   to both `ClientsAdmin.jsx`'s "Add a client" form and its "Add Enquiry" form, placed
   after the existing fields. Not required (this is a catch-all, not a mandatory field
   like the Opportunity follow-up date). Existing clients/opportunities get an inline
   edit-and-save control for `notes`, same pattern as the follow-up/consent rows already
   use.
4. **Not audit-logged** -- a free-text convenience field, same non-audited convention as
   `follow_up_note` and `Project.custom_notes`, not a governance-relevant fact like
   blacklist/consent.

### Explicitly out of scope
- No character limit enforced beyond `Text`'s natural database ceiling (no arbitrary
  `String(N)` truncation) -- this is a catch-all note, not a structured short field.
- No change to `follow_up_note`/`lost_reason`'s own meaning or usage; `notes` is additive,
  not a replacement.

### Acceptance criteria
- "Add a client" and "Add Enquiry" both show a multi-line Notes/remarks box; submitting
  with it blank works exactly as today (fully optional).
- A client/opportunity's notes can be set at creation and edited afterward independently
  of its follow-up date/note.
- No existing Client/Opportunity test regresses; new tests cover creation-with-notes,
  editing notes afterward, and role gates matching each entity's existing write role set.

### Open decisions (proposed defaults)
1. **Separate `PATCH .../notes` endpoint vs. folding into an existing one**: proposed a
   new narrow endpoint per entity (as above) -- consistent with this register's own
   established one-endpoint-per-concern convention (`follow-up`, `consent`, `link-client`
   are all already separate).

### Approval
☐ Approved as proposed, all decisions
☐ Approved with changes (noted above)
☐ Not approved

**Prepared by:** R. Patni (with AI development assistance)
**Date:** 23 September 2026
