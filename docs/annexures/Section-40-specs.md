# Section 40 — Draft Specifications for Director Approval

**Date: 21 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same seventh proactive gap audit as Sections
38-39, spot-verified against the live code before being registered as Amendment No. 34.

---

## Amendment No. 34 — Vendor Master Has No Deactivation and No Duplicate-Vendor Guard

**Registered scope (Annexure 2, §Amendment 34):** `Vendor` has no `is_active` column
(unlike `Hub`, which follows exactly this convention) and no delete endpoint, so a
vendor can never be retired; `create_vendor` has no duplicate check on `name`/`gstin`
(unlike `create_hub`'s explicit `409` in the same codebase).

### Current state (verified against `backend/app/models/vendor.py` full read and
`backend/app/api/vendors.py` full read)

```python
# vendors.py
@vendors_router.post("", response_model=VendorOut, status_code=201)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
):
    vendor = Vendor(**payload.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor
```

Compare `hubs.py`'s `create_hub`:
```python
if db.query(Hub).filter(Hub.name == payload.name).first():
    raise HTTPException(status_code=409, detail=f"A hub named '{payload.name}' already exists")
```
and `Hub`'s own `is_active` column plus `list_hubs`'s `include_inactive` query param.
`Vendor` has neither: no `is_active` field exists anywhere in the model (confirmed by
grep), and `vendors.py` registers no `DELETE` route for a vendor (only for a vendor's
`Product` rows). A vendor selectable in RFQ/PO/Price Request flows can never be marked
"we no longer use this vendor," and two vendors can be created with the identical name
(or the identical real GSTIN) with no warning.

### Proposed spec

1. **New nullable-safe `Vendor.is_active: bool` column, default `True`** (existing
   vendors stay usable -- unlike Amendment 28's `is_calibration`, which defaulted
   `False` since it flags an exception; here the exception is the retired vendor, so the
   default is the opposite):
   ```python
   is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
   ```
   ```python
   # migration
   op.add_column('vendors', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
   op.alter_column('vendors', 'is_active', server_default=None)
   ```
2. **`VendorOut` gains `is_active: bool`; `VendorUpdate` gains `is_active: bool | None =
   None`** -- no other code change needed in `update_vendor`, since it already applies
   every field in `payload.model_dump(exclude_unset=True)` generically.
3. **`list_vendors` gains `include_inactive: bool = False`, filtering `Vendor.is_active.is_(True)`
   by default** -- same shape as `list_hubs`:
   ```python
   @vendors_router.get("", response_model=list[VendorOut])
   def list_vendors(
       include_inactive: bool = False,
       db: Session = Depends(get_db),
       current_user=Depends(require_roles(*PROCUREMENT_ROLES)),
   ):
       query = db.query(Vendor)
       if not include_inactive:
           query = query.filter(Vendor.is_active.is_(True))
       return query.order_by(Vendor.name).all()
   ```
   Deactivation (not deletion) is the intended way to retire a vendor -- matching this
   app's existing write-once/supersede convention for master-data rows (`Hub`,
   `ClientSignatory`) rather than introducing a delete path this codebase otherwise
   avoids for referenced master data.
4. **`create_vendor` gains a duplicate check, mirroring `create_hub`'s exact pattern**:
   ```python
   if db.query(Vendor).filter(Vendor.name == payload.name).first():
       raise HTTPException(status_code=409, detail=f"A vendor named '{payload.name}' already exists")
   if payload.gstin and db.query(Vendor).filter(Vendor.gstin == payload.gstin).first():
       raise HTTPException(status_code=409, detail=f"A vendor with GSTIN '{payload.gstin}' already exists")
   ```
   The `gstin` check only fires when `payload.gstin` is set -- `gstin=None` legitimately
   means "unregistered" (per `Vendor`'s own docstring) and multiple unregistered vendors
   are not duplicates of each other just for sharing a null GSTIN.

**Acceptance criteria:** a vendor can be deactivated via `PATCH /vendors/{id}` with
`is_active: false` and disappears from the default `GET /vendors` listing (still
retrievable with `include_inactive=true` or by direct `GET /vendors/{id}`); creating a
vendor with a `name` that already exists is rejected with `409`; creating a vendor with
a `gstin` that already exists on another vendor is rejected with `409`; two vendors with
`gstin=None` can coexist without error; an existing vendor's `is_active` defaults to
`True` after migration, unaffected by this change.

### Open decisions — need Director input before implementation

1. **Confirm `is_active` deactivation (no delete) as the retirement mechanism**,
   matching `Hub`/`ClientSignatory`'s existing convention, rather than a hard delete.
   Proposed: deactivation -- a vendor may be referenced by historical Price
   Requests/POs/RateHistory rows that must keep resolving correctly.
2. **Confirm the duplicate check is exact-match on `name`** (proposed, matching
   `create_hub`'s own exact-match, case-sensitive check) rather than a case-insensitive
   or fuzzy match, which risks false positives on legitimately distinct vendors with
   similar names.
3. **Confirm blocking (not just warning) on a duplicate `name`/`gstin` at creation**,
   same `409` severity `create_hub` already uses, rather than allowing it through with a
   warning.

---

## Approval

Amendment 34 (Vendor deactivation + duplicate guard): ☑ Approved — "approve as proposed,
all decisions" (21 September 2026)

Decision 1 (deactivation, not delete): ☑ Resolved as proposed.
Decision 2 (exact-match duplicate check on `name`): ☑ Resolved as proposed.
Decision 3 (block, not warn, on duplicate `name`/`gstin`): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 21 September 2026
