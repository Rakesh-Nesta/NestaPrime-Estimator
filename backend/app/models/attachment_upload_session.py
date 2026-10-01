import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UploadSessionStatus(str, enum.Enum):
    """P4 contract v7, Section 4. uploading -> completing -> completed |
    failed; completing -> uploading is recovery (Section 0.A), gated by
    completion_attempt; uploading -> purging is cleanup's own atomic
    claim."""

    UPLOADING = "uploading"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    PURGING = "purging"


class ChunkStatus(str, enum.Enum):
    PENDING_WRITE = "pending_write"
    WRITTEN = "written"


class AttachmentUploadSession(Base):
    """P4 contract v7, Section 4. A chunked-upload attempt against one
    doc_type/doc_id target. declared_sha256 is REQUIRED here (unlike the
    single-shot upload path, which computes its hash server-side from a
    complete file) -- see Section 0 item 1. completion_attempt is the
    fencing token: bumped atomically with BOTH the uploading->completing
    transition (a new completion attempt) and, per revision 5/7, the
    completing->uploading transition (recovery) -- never left to drift
    apart from the status change it accompanies."""

    __tablename__ = "attachment_upload_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_size: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=UploadSessionStatus.UPLOADING.value)
    completion_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resulting_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    temp_files_purged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )


class AttachmentUploadChunk(Base):
    """P4 contract v7, Section 4. claimed_attempt (revision 5/7 fix) is
    bumped every time this chunk_index is (re)claimed by a write attempt;
    promotion to the single accepted chunk path is only permitted while
    claimed_attempt still matches, under the session-then-chunk lock
    order (revision 6 fix)."""

    __tablename__ = "attachment_upload_chunks"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachment_upload_sessions.id"), primary_key=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'pending_write' is 13 chars -- String(12) (matching an earlier miscount in the contract's
    # own wire-block) was caught only once a real database rejected the insert; widened to 20.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ChunkStatus.PENDING_WRITE.value)
    claimed_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
