import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StageStatus(str, enum.Enum):
    """P4 contract v7, Section 3. Stored as a plain VARCHAR (not a Postgres
    enum), deliberately -- every transition here is a simple CAS-style
    UPDATE ... WHERE status=X, and a plain string avoids the enum-ADD-VALUE
    friction a real Postgres enum type would add for no benefit this table
    actually needs."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    EVIDENCE_SUBMITTED = "evidence_submitted"
    REJECTED = "rejected"
    REVIEWED = "reviewed"


class ProjectConstructionStage(Base):
    """P4 contract v7, Section 3. One row per (project, phase) -- phase
    values match ConstructionSequenceStep's own ConstructionPhase enum
    (construction_sequence_step.py), stored here as a plain string rather
    than a shared Postgres enum type, so this table's own lifecycle never
    depends on that catalog table's. Seeded for every new project inside
    create_project (projects.py); backfilled once, migration-time, for
    every project that already existed (509d1202ac03)."""

    __tablename__ = "project_construction_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StageStatus.NOT_STARTED.value)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evidence_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evidence_submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "phase", name="uq_project_construction_stage_project_phase"),)
