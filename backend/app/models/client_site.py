import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientSite(Base):
    """P2 Client 360: a named site/location belonging to a Client. A Project may select one
    (Project.site_id) -- that copies the Site's address fields into the Project's own existing
    city/site_address/site_state_code columns once, at that moment. site_id afterward is
    provenance metadata, not a live reference: a later edit here never retroactively changes a
    Project that already copied from it."""

    __tablename__ = "client_sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    site_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    site_state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
