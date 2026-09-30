import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DismissedDuplicatePair(Base):
    """P2 Client 360: a suggested-duplicate Client pair a user has dismissed. Suggestion is
    display-only (no merge action exists) -- dismissing removes a pair from the suggestion list
    for every viewer (global, not personal to the dismisser). client_id_a is always the
    lexicographically smaller id: the API normalises before every insert/lookup, so a reversed
    pair can never be stored as a second row (the composite primary key enforces it at the DB
    level once normalised)."""

    __tablename__ = "dismissed_duplicate_pairs"

    client_id_a: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), primary_key=True)
    client_id_b: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), primary_key=True)
    dismissed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
