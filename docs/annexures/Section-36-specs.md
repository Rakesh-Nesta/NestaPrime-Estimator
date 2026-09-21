# Section 36 — Draft Specifications for Director Approval

**Date: 21 September 2026 | Status: DRAFT — specification only, per Annexure 2's Change
Process (Part 1): "Director approves → complete amended specification prepared. Only
then implement." Implementation starts once approved below.**

Scope note: self-identified during the same sixth proactive gap audit as Section 35,
spot-verified against the live code before being registered as Amendment No. 30.

---

## Amendment No. 30 — Report Release Has No Audit Trail, Unlike the Identical Quotation-Release Pattern

**Registered scope (Annexure 2, §Amendment 30):** `release_report` (Director-only,
DRAFT -> RELEASED) never imports or calls `write_audit_log_entry`.

### Current state (verified against `backend/app/api/reports.py:647-665`, direct read;
confirmed no `write_audit_log_entry` import anywhere in the file by grep)

```python
@router.post("/{report_id}/release", response_model=ReportOut)
def release_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("director")),
):
    """T.2 rule 4: Director-only, mirrors the Cost Sheet verification gate."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != ReportStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot release a report in {report.status.value} status")

    report.status = ReportStatus.RELEASED
    report.released_by_id = current_user.id
    report.released_at = datetime.now(UTC)
    db.commit()
    db.refresh(report)
    return report
```

The exactly analogous status-transition endpoint elsewhere in the codebase,
`release_quotation` (`backend/app/api/documents.py:2443-2498`), logs its DRAFT ->
RELEASED transition via `write_audit_log_entry` -- there, conditionally, only when the
release needed Director sign-off specifically (a PM can release a normal Quotation).
`release_report` has no such PM/Director split -- it is *already* Director-only for
every release -- so the parallel case here is simpler: every release is the governance
event, not just some of them. Margin/Override Summary reports carry cost/margin and
override-frequency data restricted to PM/Director (`VISIBLE_ROLES`); releasing one is a
governance action currently recorded nowhere except the row's own
`released_by_id`/`released_at`, which the audit log UI never surfaces.

### Proposed spec

1. **Import `write_audit_log_entry` and `Request`, add a `request: Request` parameter
   to `release_report`, and log the transition unconditionally** (every release is
   already Director-only, unlike Quotation's conditional case):
   ```python
   @router.post("/{report_id}/release", response_model=ReportOut)
   def release_report(
       report_id: uuid.UUID,
       request: Request,
       db: Session = Depends(get_db),
       current_user=Depends(require_roles("director")),
   ):
       report = db.query(Report).filter(Report.id == report_id).first()
       if not report:
           raise HTTPException(status_code=404, detail="Report not found")
       if report.status != ReportStatus.DRAFT:
           raise HTTPException(status_code=400, detail=f"Cannot release a report in {report.status.value} status")

       write_audit_log_entry(
           db, current_user, "report", report.id, "status",
           old_value=report.status.value, new_value=ReportStatus.RELEASED.value,
           request=request,
       )

       report.status = ReportStatus.RELEASED
       report.released_by_id = current_user.id
       report.released_at = datetime.now(UTC)
       db.commit()
       db.refresh(report)
       return report
   ```
2. **No `reason` text needed** -- unlike Quotation's conditional case (which explains
   *why* Director sign-off was required), every report release here is Director-only by
   definition, so there's nothing extra to explain; `old_value`/`new_value` alone
   (`draft` -> `released`) carry the full meaning.
3. **No change to `release_report`'s actual behavior** -- same DRAFT-only guard, same
   Director-only role gate, same fields set on the row.

**Acceptance criteria:** releasing a report writes one audit log entry (`status`:
`draft` -> `released`, the acting Director, a timestamp), retrievable via `GET
/audit-log` filtered to `document_type=report, document_id=<report_id>`; no change to
the release guard, role gate, or the report's own `released_by_id`/`released_at` fields.

### Open decisions — need Director input before implementation

1. **Confirm `document_type="report"`** as the audit-log category, matching the
   pattern every other document type in this codebase already uses (`"estimate"`,
   `"quotation"`, `"price_request"`, `"client"`).

---

## Approval

Amendment 30 (report release audit trail): ☑ Approved — "approve as proposed, all
decisions" (21 September 2026)

Decision 1 (`document_type="report"`): ☑ Resolved as proposed.

Director Name: ______________________ Signature: ______________________ Date: ____________

Prepared by: R. Patni (with AI development assistance) | Date: 21 September 2026
