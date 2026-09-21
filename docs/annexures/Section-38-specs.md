# Section 38 — Draft Specifications for Director Approval

**Date: 21 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during a seventh Director-requested proactive gap audit
against the register, spot-verified against the live code before being registered as
Amendment No. 32.

---

## Amendment No. 32 — Master Settings Override's Amendment-22 Numeric Guard Is Bypassable

**Registered scope (Annexure 2, §Amendment 32):** `create_override`'s numeric-consistency
check only inspects the caller-supplied `master_value` field, never the real, current
Master Setting value -- a fabricated `master_value` skips the check entirely.

### Current state (verified against `backend/app/api/settings.py:377-427`, direct read)

```python
class OverrideCreate(BaseModel):
    document_type: DocumentType
    document_id: uuid.UUID
    setting_key: str
    master_value: str
    override_value: str
    reason: str = Field(min_length=1)

@overrides_router.post("", response_model=OverrideOut, status_code=201)
def create_override(
    payload: OverrideCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*OVERRIDE_ROLES)),
):
    try:
        float(payload.master_value)
    except ValueError:
        pass
    else:
        try:
            float(payload.override_value)
        except ValueError:
            raise HTTPException(status_code=422, ...) from None

    override = Override(
        document_type=payload.document_type,
        document_id=payload.document_id,
        setting_key=payload.setting_key,
        master_value=payload.master_value,
        ...
    )
```

`payload.master_value` is entirely caller-supplied -- the function never calls the
already-existing `get_current_setting_value(db, payload.setting_key)` to check what the
Master Setting's value actually is. A PM/Director can send a fabricated non-numeric
`master_value` (e.g. `"n/a"`) for a `setting_key` that is genuinely numeric (e.g.
`gst_rate_percent`), which skips the `try: float(...) except ValueError: pass` branch
entirely and lets any non-numeric `override_value` through -- reopening the write-time
gap Amendment 22 was built to close. The persisted `Override.master_value` is also just
whatever the caller sent, not the real value it claims to record ("the master value it
replaced," per `Override`'s own docstring).

### Proposed spec

1. **Look up the real current value server-side and use it for both the check and the
   persisted record**, ignoring the client-supplied `master_value` for anything other
   than display convenience:
   ```python
   real_master_value = get_current_setting_value(db, payload.setting_key)
   if real_master_value is None:
       raise HTTPException(
           status_code=404, detail=f"No Master Setting found for key '{payload.setting_key}'"
       )
   try:
       float(real_master_value)
   except ValueError:
       pass
   else:
       try:
           float(payload.override_value)
       except ValueError:
           raise HTTPException(
               status_code=422,
               detail=(
                   f"'{payload.setting_key}' is a numeric setting (current value "
                   f"'{real_master_value}') -- override_value ('{payload.override_value}') must be numeric too"
               ),
           ) from None

   override = Override(
       document_type=payload.document_type,
       document_id=payload.document_id,
       setting_key=payload.setting_key,
       master_value=real_master_value,  # server-computed, not the caller's copy
       override_value=payload.override_value,
       reason=payload.reason,
       user_id=current_user.id,
   )
   ```
2. **`OverrideCreate.master_value` is removed from the request schema** -- there is
   nothing left for the client to legitimately supply it for once the server always
   computes the real value; keeping an unused field around would just leave a second,
   inert path back to the same confusion.
3. **A `setting_key` with no matching Setting row is rejected with `404`** -- closes the
   secondary gap noted in the registered scope (no check that `setting_key` corresponds
   to a real Setting).
4. **`document_id`/`document_type` existence is explicitly left unvalidated** -- see Open
   Decision 2 below.

**Acceptance criteria:** creating an Override for a numeric `setting_key` with a
non-numeric `override_value` is rejected with `422`, regardless of anything the client
claims about `master_value` (the field no longer exists in the request); the persisted
`Override.master_value` always matches the real Setting value at creation time; an
Override against an unknown `setting_key` is rejected with `404`; Overrides against
legitimately non-numeric settings (company details, T&C text) are unaffected.

### Open decisions — need Director input before implementation

1. **Confirm removing `master_value` from the request schema entirely** (proposed)
   rather than keeping it as an ignored/deprecated field. Proposed: remove it -- an
   accepted-but-ignored field is exactly the kind of thing that quietly drifts out of
   sync with what a future reader assumes it does.
2. **Confirm `document_id`/`document_type` existence validation stays out of scope for
   this fix.** It would need per-`DocumentType` dispatch logic (seven different tables:
   Cost Sheet, Estimate, Quotation, Work Order, Technical Bid Checklist Item, Price
   Request, Site Survey, Estimate Option) to check generically, disproportionate to the
   numeric-guard bug this Amendment actually targets. Proposed: leave as a known,
   separate gap, not fixed here.

---

## Approval

Amendment 32 (Override numeric-guard fix): ☑ Approved — "approve as proposed, all
decisions" (21 September 2026)

Decision 1 (remove `master_value` from the request schema): ☑ Resolved as proposed.
Decision 2 (document existence validation out of scope): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 21 September 2026
