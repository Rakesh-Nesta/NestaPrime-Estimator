import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLogEntry(Base):
    """Part O: 'AUDIT_LOG -- log_id, timestamp, user_id, role,
    document_type, document_id, field, old_value, new_value, reason, ip,
    session_id; append-only ... indexed on timestamp and document;
    retained 8 years.' M.5: 'change_log[] on every document: who, when,
    field, old -> new, reason (for approvals, skips, waivers, discounts).'

    Scope (an explicit, informed decision -- the blueprint itself never
    states a governing rule; it piecemeal name-checks Settings, Attachments
    and Messages as ALSO writing here despite each already having its own
    dedicated table/history, while never resolving whether that means
    'log everything' or 'log these named governance events'): this table
    covers exactly M.5's four named categories -- Estimate-option
    approvals, skip-request approvals, approval-evidence waivers, and
    Quotation discounts/below-floor Director releases -- plus Settings
    changes, which Q.2 rule 7 explicitly and unambiguously requires
    ('Settings changes are in the audit log (M.5)'). Attachments,
    Messages, RateHistory and Overrides are NOT re-logged here; each
    already has its own version/timestamp/reason tracking, and dual-
    logging them was judged lower-value than the wiring it would cost.

    document_type is a plain string (not the stricter Override/Attachment
    DocumentType enum in app.models.setting), since audit coverage spans
    things that aren't "documents" in that enum's sense (e.g. "setting",
    "skip_request"). append-only is enforced at the application level
    only (no code anywhere issues UPDATE/DELETE against this table) --
    the blueprint's own 'insert-only DB role, no update/delete grant' is
    real Postgres-permissions language with zero elaboration anywhere
    else in the document (no other table gets this treatment, no infra
    section describes setting up restricted DB roles), so a literal
    database-role-level restriction was not built; flagging this rather
    than silently deciding it for good. retention/auto-purge after the
    stated 8 years is likewise not implemented -- Appendix D lists that
    figure as 'Pending' Director sign-off, not a locked, actionable rule,
    and the document never describes a purge mechanism regardless.
    session_id stays permanently unpopulated (None) -- this app has no
    session concept beyond a stateless JWT bearer token, so there is
    nothing honest to put there; the column is kept for Part O field-
    parity, not fabricated data."""

    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
