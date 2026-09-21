# Section 37 — Draft Specifications for Director Approval

**Date: 21 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same sixth proactive gap audit as Sections 35-36,
spot-verified against the live code before being registered as Amendment No. 31.

---

## Amendment No. 31 — Client Signatory Records Have No Audit Trail At All

**Registered scope (Annexure 2, §Amendment 31):** `backend/app/api/client_signatories.py`
-- the entire file -- has no `write_audit_log_entry` import or call anywhere.

### Current state (verified against `backend/app/api/client_signatories.py`, full file
read; confirmed no `write_audit_log_entry` import by grep)

```python
@client_signatories_router.post("", response_model=ClientSignatoryOut, status_code=201)
def create_signatory(
    client_id: uuid.UUID,
    payload: ClientSignatoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    _get_client_or_404(db, client_id)
    signatory = ClientSignatory(client_id=client_id, **payload.model_dump())
    db.add(signatory)
    db.commit()
    db.refresh(signatory)
    return signatory


@client_signatories_router.patch("/{signatory_id}", response_model=ClientSignatoryOut)
def update_signatory(
    client_id: uuid.UUID,
    signatory_id: uuid.UUID,
    payload: ClientSignatoryUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*WRITE_ROLES)),
):
    _get_client_or_404(db, client_id)
    signatory = _get_signatory_or_404(db, client_id, signatory_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(signatory, field, value)
    db.commit()
    db.refresh(signatory)
    return signatory
```

`create_signatory`, and especially `update_signatory` (which can silently extend an
`expiry_date`, flip a departed employee's `is_active` back to `True`, or edit a
`designation`), have zero trail. This matters specifically because
`attachments.py`'s `_match_active_signatory` (`attachments.py:132-149`) uses these exact
rows to decide whether a client-side approval on an `approval_evidence` attachment is
considered legally valid -- an unaudited edit here can retroactively make (or break) an
approval's validity with no record of who changed what.

### Proposed spec

1. **`create_signatory` logs a creation entry** -- following the same
   "created" convention `price_requests.py`'s own creation endpoint already uses (a
   summary string as `new_value`, `old_value=None`):
   ```python
   signatory = ClientSignatory(client_id=client_id, **payload.model_dump())
   db.add(signatory)
   db.flush()  # assigns signatory.id before the audit entry references it
   write_audit_log_entry(
       db, current_user, "client_signatory", signatory.id, "created",
       old_value=None, new_value=f"{signatory.name} ({signatory.designation})",
       request=request,
   )
   db.commit()
   ```
2. **`update_signatory` logs one entry per changed field**, the same
   changed-field loop `update_client_consent`/proposed-Amendment-29's `update_client_flags`
   already use:
   ```python
   signatory = _get_signatory_or_404(db, client_id, signatory_id)
   changes = payload.model_dump(exclude_unset=True)
   for field, value in changes.items():
       old_value = getattr(signatory, field)
       if old_value != value:
           write_audit_log_entry(
               db, current_user, "client_signatory", signatory.id, field,
               old_value=old_value, new_value=value, request=request,
           )
       setattr(signatory, field, value)
   db.commit()
   ```
   This covers the specific, highest-risk case named above: an `is_active: false -> true`
   reactivation, or an `expiry_date` extension, now writes a clear, attributable entry.
3. **Both endpoints gain a `request: Request` parameter**, matching every other
   audit-logging endpoint in this codebase.
4. **`document_type="client_signatory"`, a new category** (not folded into
   `"client"`) -- a signatory is its own row with its own id, and
   `attachments.py`'s validity check is keyed off the signatory specifically, so keeping
   its audit trail separately queryable (by `document_id=<signatory_id>`) is more useful
   here than merging it into the parent client's own log.

**Acceptance criteria:** creating a signatory writes one "created" audit entry;
updating a signatory writes one entry per field that actually changed (a request that
resends the same values writes nothing new); both are retrievable via `GET /audit-log`
filtered to `document_type=client_signatory, document_id=<signatory_id>`; no change to
either endpoint's validation, role gates, or the "deactivate rather than delete"
convention already documented in `update_signatory`'s own docstring.

### Open decisions — need Director input before implementation

1. **Confirm the new `document_type="client_signatory"` category** (proposed) rather
   than folding these entries into the parent client's own `"client"` audit trail.
   Proposed: keep it separate, for the reason given in point 4 above.
2. **Confirm logging every changed field on update, including non-approval-relevant
   ones (`name`, `email`, `phone`)** -- not just the two named as highest-risk
   (`is_active`, `expiry_date`). Proposed: log all of them, matching this codebase's
   existing convention (`update_client_consent`) of logging every changed field
   uniformly rather than special-casing a subset -- simpler, and a `designation`/`name`
   edit is exactly the kind of change that could also make a stale signatory match an
   attachment it shouldn't.

---

## Approval

Amendment 31 (client signatory audit trail): ☑ Approved — "approve as proposed, all
decisions" (21 September 2026)

Decision 1 (new `document_type="client_signatory"` category): ☑ Resolved as proposed.
Decision 2 (log every changed field, not just `is_active`/`expiry_date`): ☑ Resolved as
proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 21 September 2026
