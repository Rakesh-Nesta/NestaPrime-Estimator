import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanyLogo(Base):
    """Part O COMPANY.logo / R.0 checklist: 'Logo (SVG/PNG) ... for PDF.'
    COMPANY's other fields (legal name, PAN, GSTIN, bank details) already
    live as plain Master Settings (see pdf_documents.py's
    _COMPANY_SETTING_FIELDS) since they're short text values -- a logo is
    binary file content instead, so it gets its own small table rather
    than trying to fit through Setting.value.

    Single-tenant app, so there is always exactly one CURRENT logo (the
    most recent row by uploaded_at) -- but M.3's own 'no overwrite, no
    delete' discipline still applies: uploading a new logo inserts a new
    row rather than mutating the old one, so who uploaded what and when
    stays in the audit trail."""

    __tablename__ = "company_logo"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)

    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
