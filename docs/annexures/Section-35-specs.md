# Section 35 — Draft Specifications for Director Approval

**Date: 21 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a sixth Director-requested proactive gap audit
against the register, spot-verified against the live code before being registered as
Amendment No. 29.

---

## Amendment No. 29 — Director Can Silently Flip a Client's Blacklist/Overdue Flags With No Audit Trail

**Registered scope (Annexure 2, §Amendment 29):** `update_client_flags` (the
Director-only `PATCH /clients/{client_id}` that sets `overdue_flag`/`blacklist_flag`)
calls `db.commit()` directly with no `write_audit_log_entry` call and no `request`
parameter at all.

### Current state (verified against `backend/app/api/clients.py:165-186`, direct read)

```python
@router.patch("/{client_id}", response_model=ClientOut)
def update_client_flags(
    client_id: uuid.UUID,
    payload: ClientFlagsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("director")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.overdue_flag is not None:
        client.overdue_flag = payload.overdue_flag
    if payload.blacklist_flag is not None:
        client.blacklist_flag = payload.blacklist_flag

    db.commit()
    db.refresh(client)
    return client
```

The very next function in the same file, `update_client_consent` (`clients.py:189-219`),
does the correct thing: it takes a `request: Request` parameter and calls
`write_audit_log_entry` for every changed field, using
`payload.model_dump(exclude_unset=True)`. `update_client_flags` is structurally
identical (same `ClientFlagsUpdate`/`ClientConsentUpdate` shape: both fields
`bool | None = None`) but skips that entirely. These two flags gate real financial
controls: `blacklist_flag` blocks new Estimate creation
(`documents.py:1459`, `:2096`), `overdue_flag` blocks Quotation release
(`documents.py:2465`) -- Part O's own stated purpose for both.

### Proposed spec

1. **Mirror `update_client_consent`'s existing pattern exactly** -- add a
   `request: Request` parameter to `update_client_flags`, and replace the two `if ... is
   not None` assignments with the same changed-field loop already used one function
   below:
   ```python
   def update_client_flags(
       client_id: uuid.UUID,
       payload: ClientFlagsUpdate,
       request: Request,
       db: Session = Depends(get_db),
       current_user=Depends(require_roles("director")),
   ):
       client = db.query(Client).filter(Client.id == client_id).first()
       if not client:
           raise HTTPException(status_code=404, detail="Client not found")

       changes = payload.model_dump(exclude_unset=True)
       for field, value in changes.items():
           old_value = getattr(client, field)
           if old_value != value:
               write_audit_log_entry(
                   db, current_user, "client", client.id, field,
                   old_value=old_value, new_value=value, request=request,
               )
           setattr(client, field, value)

       db.commit()
       db.refresh(client)
       return client
   ```
2. **No new behavior, no new validation** -- this is a pure logging addition; the
   endpoint's actual effect (which flags get set, who can call it, what it blocks) is
   completely unchanged.
3. **`document_type="client"`, matching `update_client_consent`'s own convention** --
   both endpoints mutate the same `Client` row, so audit entries for consent fields and
   flag fields end up in the same, single per-client audit trail rather than two
   separate ones.

**Acceptance criteria:** setting or clearing `overdue_flag`/`blacklist_flag` via `PATCH
/clients/{client_id}` writes one audit log entry per changed field (old value, new
value, the acting Director, a timestamp), retrievable via the existing `GET /audit-log`
endpoint filtered to `document_type=client, document_id=<client_id>`; a request that
sets a flag to the value it already had writes no entry (matching
`update_client_consent`'s existing "only log real changes" behavior); no change to
either flag's actual effect on Estimate creation or Quotation release.

### Open decisions — need Director input before implementation

1. **Confirm reusing `document_type="client"`** (proposed, matching
   `update_client_consent`) rather than a separate `document_type` such as
   `"client_flags"`. Proposed: reuse `"client"` -- keeps one client's full history (both
   consent and flag changes) in one place when filtering the audit log by that client.

---

## Approval

Amendment 29 (client flags audit trail): ☑ Approved — "approve as proposed, all
decisions" (21 September 2026)

Decision 1 (reuse `document_type="client"`): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 21 September 2026
