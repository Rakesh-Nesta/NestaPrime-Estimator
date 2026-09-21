# Section 39 — Draft Specifications for Director Approval

**Date: 21 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same seventh proactive gap audit as Section 38,
spot-verified against the live code before being registered as Amendment No. 33.

---

## Amendment No. 33 — Skip Request Workflow Has No Reject Path, Can Deadlock a Project

**Registered scope (Annexure 2, §Amendment 33):** `SkipRequestStatus` has only
`PENDING`/`APPROVED`; no reject/decline endpoint exists anywhere. A pending request a
PM/Director doesn't want to approve blocks all future skip requests on that project
forever, with no record a decision was ever made.

### Current state (verified against `backend/app/models/skip_request.py` and
`backend/app/api/skip_requests.py`, full file reads)

```python
class SkipRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
```

```python
# skip_requests.py -- create_skip_request
pending = (
    db.query(SkipRequest)
    .filter(SkipRequest.project_id == project_id, SkipRequest.status == SkipRequestStatus.PENDING)
    .first()
)
if pending:
    raise HTTPException(status_code=400, detail="A skip request is already pending for this project")
```

Only `create_skip_request`, `list_skip_requests`, and `approve_skip_request` exist --
confirmed by reading the full router file and by grepping the frontend
(`Documents.jsx`/`api.js`), which only wires up `approveSkipRequest`. There is no way to
close out a `PENDING` request a PM/Director decides not to approve, so it blocks every
future skip request on that project permanently. Separately: `create_cost_sheet`
(`documents.py`) has no check for a `PENDING` `SkipRequest` at all, so a normal, full
Cost Sheet can be built directly while a skip request sits pending -- the two paths can
silently diverge with no interaction between them.

### Proposed spec

1. **Add `REJECTED` to `SkipRequestStatus`** (Postgres enum, requires a migration):
   ```python
   class SkipRequestStatus(str, enum.Enum):
       PENDING = "pending"
       APPROVED = "approved"
       REJECTED = "rejected"
   ```
   ```python
   # migration
   op.execute("ALTER TYPE skip_request_status ADD VALUE IF NOT EXISTS 'REJECTED'")
   op.add_column('skip_requests', sa.Column('rejection_reason', sa.String(length=500), nullable=True))
   ```
2. **New `POST /skip-requests/{skip_request_id}/reject` endpoint**, same `APPROVE_ROLES`
   (PM/Director) as approval, requiring a reason:
   ```python
   class SkipRequestReject(BaseModel):
       reason: str = Field(min_length=1, max_length=500)

   @skip_requests_router.post("/skip-requests/{skip_request_id}/reject", response_model=SkipRequestOut)
   def reject_skip_request(
       skip_request_id: uuid.UUID,
       payload: SkipRequestReject,
       request: Request,
       db: Session = Depends(get_db),
       current_user=Depends(require_roles(*APPROVE_ROLES)),
   ):
       skip_request = db.query(SkipRequest).filter(SkipRequest.id == skip_request_id).first()
       if not skip_request:
           raise HTTPException(status_code=404, detail="Skip request not found")
       if skip_request.status != SkipRequestStatus.PENDING:
           raise HTTPException(status_code=400, detail="This skip request has already been decided")

       skip_request.status = SkipRequestStatus.REJECTED
       skip_request.rejection_reason = payload.reason
       skip_request.decided_at = datetime.now(UTC)

       write_audit_log_entry(
           db, current_user, "skip_request", skip_request.id, "status",
           old_value=SkipRequestStatus.PENDING.value, new_value=SkipRequestStatus.REJECTED.value,
           reason=payload.reason, request=request,
       )

       db.commit()
       db.refresh(skip_request)
       return skip_request
   ```
   `approved_by_id` is left `None` on a rejection (it specifically means "who approved");
   the acting user is already captured by the audit log entry, same as every other
   status-transition endpoint in this codebase.
3. **Once rejected, a new skip request can be raised for the same project** -- no code
   change needed here: `create_skip_request`'s own pending-check already only filters on
   `status == PENDING`, so a `REJECTED` row doesn't block a fresh request. This is what
   actually closes the deadlock.
4. **`create_cost_sheet` (the normal, non-skip path) rejects while a skip request is
   `PENDING`** -- closes the "silently diverge" gap, symmetric with `create_skip_request`
   already rejecting when an active Cost Sheet exists:
   ```python
   pending_skip = (
       db.query(SkipRequest)
       .filter(SkipRequest.project_id == project_id, SkipRequest.status == SkipRequestStatus.PENDING)
       .first()
   )
   if pending_skip:
       raise HTTPException(
           status_code=400,
           detail="A skip request is pending for this project -- approve or reject it first",
       )
   ```

**Acceptance criteria:** a PM/Director can reject a pending skip request with a required
reason, writing an audit log entry; a rejected request no longer blocks a new skip
request on the same project; attempting to build a normal Cost Sheet while a skip
request is pending is rejected with a clear `400`, symmetric with the existing reverse
guard; an already-decided (approved or rejected) skip request cannot be rejected again.

### Open decisions — need Director input before implementation

1. **Confirm adding `create_cost_sheet`'s new guard** (point 4 above) as part of this
   fix, rather than a separate future Amendment. Proposed: include it here -- it is the
   direct cause of the "two paths silently diverge" half of the registered gap, and the
   fix is small (one query, mirroring an existing pattern in the same file).
2. **Confirm `rejection_reason` as a separate column** rather than reusing the existing
   `reason` field (which holds the original *request* justification, not the decision).
   Proposed: separate column -- overwriting the requester's own stated reason with the
   approver's decision reason would destroy the original record.

---

## Approval

Amendment 33 (Skip Request reject path): ☑ Approved — "approve as proposed, all
decisions" (21 September 2026)

Decision 1 (`create_cost_sheet` guard included in this fix): ☑ Resolved as proposed.
Decision 2 (separate `rejection_reason` column): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 21 September 2026
