# Section 48 — Spec Doc

## Amendment No. 42 — Client Follow-Up Date (Leads & Clients, Header Index Step 3)

**Registered scope:** see `docs/annexures/Annexure-2.md`, Amendment No. 42. This is the
concrete deliverable for Section E step 3 (Leads & Clients) -- the "re-home" half of that
step is already done (Amendment 36); this is the new capability half.

### Current state

`backend/app/models/client.py`: no due-date/reminder field of any kind. `ClientsAdmin.jsx`
has no general edit capability at all -- only create, `updateClientFlags` (Director-only,
blacklist/overdue), and `updateClientConsent` (WhatsApp/email/Telegram opt-in) exist.
`Sidebar.jsx`'s "Leads & Clients" item already routes here since Amendment 36.

### Proposed spec

1. `Client` gains two nullable columns: `next_follow_up_date` (Date) and
   `follow_up_note` (String, short -- e.g. "Discuss pricing," "Send updated quote").
   A bare date with no context is less useful to a rep juggling many leads than one
   with a one-line reminder attached.
2. New endpoint `PATCH /clients/{client_id}/follow-up`, payload
   `{next_follow_up_date, follow_up_note}`, both optional/nullable (clearing a follow-up
   is setting it to `null`, same pattern as every other nullable field in this app).
   Role gate: `sales`/`pm`/`director` -- same set `create_client` already uses, since
   Sales is the primary daily user of this field, not Director-only like the flags
   endpoint.
3. `ClientOut` gains both fields.
4. `ClientsAdmin.jsx`: each client row gains an inline follow-up control -- a date input
   + the note field, saved via the new endpoint. A row whose `next_follow_up_date` is in
   the past is visually flagged (e.g. red/amber text), matching this app's existing
   status-pill conventions.
5. **Explicitly not mandatory.** This is a simple, optional reminder on an existing
   Client record -- distinct from the mandatory-follow-up-date discipline already
   decided for the future `Opportunity` entity (Section E step 5), which is a different,
   stricter rule for a different, not-yet-built entity. Retrofitting "mandatory" onto
   every existing Client here would be new scope this amendment doesn't cover.
6. **Not audit-logged.** Unlike `blacklist_flag`/`overdue_flag` (Amendment 29) or
   consent changes (governance/compliance-relevant, DPDP Act), a follow-up date is a
   routine personal reminder a rep will update often -- logging every change would add
   noise to the audit trail without adding oversight value. Consistent with this
   register's own principle (Amendment 4's "Recent Activity... noise, not signal")
   of not instrumenting things nobody needs to review later.

**Acceptance criteria:**
- A Sales/PM/Director user can set, edit, and clear a client's follow-up date and note
  from Client Admin.
- A client with an overdue follow-up date is visually distinguishable from one that
  isn't.
- No audit log entries are created by this endpoint.
- `ClientOut` responses include both new fields for every role that can already read a
  client (no new exposure of anything K.3-protected -- these fields carry no cost/margin
  data).

### Open decisions

1. **Role gate: sales/pm/director (proposed default) vs. Director-only, matching the
   flags endpoint?** Proposed default: **sales/pm/director** -- this field exists
   specifically because Sales is the one who needs it day to day; gating it to Director
   would defeat the purpose.
2. **Include the note field (proposed default) vs. date only?** Proposed default:
   **include it** -- cheap to add, meaningfully more useful.
3. **Audit logging: skip it (proposed default) vs. log every change like flags/consent?**
   Proposed default: **skip it** -- see reasoning in the proposed spec above.

## Approval

☑ Approved — "approve as proposed, all decisions" (23 September 2026).

---
Prepared by: R. Patni (with AI development assistance) | Date: 23 September 2026
