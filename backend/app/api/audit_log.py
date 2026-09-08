import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLogEntry

audit_log_router = APIRouter(prefix="/audit-log", tags=["audit-log"])

# M.5: "Exportable for Director review" is the only role the blueprint
# ever names in connection with the audit log -- no PM/other-role view
# permission is stated anywhere, so this follows the Director-only
# pattern used by every other governance report in Part Q/T rather than
# guessing a broader default.
ROLES = ("director",)


def write_audit_log_entry(
    db: Session,
    current_user,
    document_type: str,
    document_id: uuid.UUID | None,
    field: str,
    old_value: object,
    new_value: object,
    reason: str | None = None,
    request: Request | None = None,
) -> None:
    """Part O AUDIT_LOG. Does not commit -- the caller's own db.commit()
    for the change being recorded covers this row too, in the same
    transaction, so an audit entry can never exist for a change that
    didn't happen (or vice versa). old_value/new_value are stringified
    here so callers can pass through whatever type the field naturally
    is (bool, Decimal, enum, ...)."""
    db.add(
        AuditLogEntry(
            user_id=current_user.id,
            role=current_user.role.value,
            document_type=document_type,
            document_id=document_id,
            field=field,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            reason=reason,
            ip=request.client.host if request is not None and request.client else None,
        )
    )


class AuditLogEntryOut(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    user_id: uuid.UUID
    role: str
    document_type: str
    document_id: uuid.UUID | None
    field: str
    old_value: str | None
    new_value: str | None
    reason: str | None
    ip: str | None
    session_id: str | None

    model_config = ConfigDict(from_attributes=True)


def _filtered_query(db: Session, document_type: str | None, document_id: uuid.UUID | None):
    query = db.query(AuditLogEntry)
    if document_type:
        query = query.filter(AuditLogEntry.document_type == document_type)
    if document_id:
        query = query.filter(AuditLogEntry.document_id == document_id)
    return query.order_by(AuditLogEntry.timestamp.desc())


@audit_log_router.get("", response_model=list[AuditLogEntryOut])
def list_audit_log(
    document_type: str | None = None,
    document_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    return _filtered_query(db, document_type, document_id).all()


@audit_log_router.get("/export")
def export_audit_log(
    document_type: str | None = None,
    document_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*ROLES)),
):
    """M.5: 'Exportable for Director review.' CSV -- the blueprint names
    no specific export format anywhere for the audit log (unlike, say,
    Master Settings' explicit 'exportable to Excel'), so the simplest,
    most universally-openable tabular format was chosen rather than
    inventing an unspecified PDF/Excel layout."""
    entries = _filtered_query(db, document_type, document_id).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["timestamp", "user_id", "role", "document_type", "document_id", "field", "old_value", "new_value", "reason", "ip"]
    )
    for e in entries:
        writer.writerow(
            [e.timestamp.isoformat(), e.user_id, e.role, e.document_type, e.document_id, e.field, e.old_value, e.new_value, e.reason, e.ip]
        )

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
