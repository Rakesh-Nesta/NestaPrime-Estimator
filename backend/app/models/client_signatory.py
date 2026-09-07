import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientSignatory(Base):
    """Part O CLIENT_SIGNATORIES. M.3's approval check matches an
    approval_evidence attachment's recorded signatory name+designation
    against an active row here (authorization_date <= the approval date,
    expiry_date null or later) -- see attachments.py's
    _match_active_signatory."""

    __tablename__ = "client_signatories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    authorization_date: Mapped[date] = mapped_column(Date, nullable=False)
    authorization_doc_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
