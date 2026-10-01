"""P5 contract revision 7: Agreement & Execution Starter.

Status columns are plain VARCHARs with Python string constants (the same choice P4 made for
project_construction_stages): every transition is an explicit, lock-protected service-layer rule, and
a plain string avoids Postgres enum ADD VALUE friction for no benefit these tables need.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class AgreementStatus:
    DRAFTED = "drafted"
    CLIENT_SIGNED = "client_signed"
    EXECUTED = "executed"
    SUPERSEDED = "superseded"
    VOIDED = "voided"
    LEGACY_ADOPTED = "legacy_adopted"

    ALL = (DRAFTED, CLIENT_SIGNED, EXECUTED, SUPERSEDED, VOIDED, LEGACY_ADOPTED)
    # Rows that no longer count as the quotation's single "current" revision (Section 4.1).
    NOT_CURRENT = (SUPERSEDED, VOIDED)
    # A correction (supersede) is only meaningful once a signature exists (Section 4.1).
    CORRECTABLE = (CLIENT_SIGNED, EXECUTED)


class Agreement(Base):
    """One current (non-superseded, non-voided) revision per Work-Order-bound quotation, enforced by a
    partial unique index; every earlier revision is retained as history, never deleted or rewritten.

    evidence_locked_at is set exactly once, at the first signature, and never cleared -- the generic
    attachment-supersede guard keys off it, not off the row's current status."""

    __tablename__ = "agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=False)
    # Denormalized from quotation.project_id at creation; read-only, used for ownership scoping.
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AgreementStatus.DRAFTED)

    client_signatory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_signatories.id"), nullable=True
    )
    client_signatory_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_signatory_designation_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    nesta_signed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    nesta_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    signed_document_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    signed_document_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index(
            "uq_agreements_one_current_per_quotation",
            "quotation_id",
            unique=True,
            postgresql_where=text("status NOT IN ('superseded', 'voided')"),
        ),
        Index("ix_agreements_signed_document_attachment_id", "signed_document_attachment_id"),
        CheckConstraint(
            "status IN ('drafted','client_signed','executed','superseded','voided','legacy_adopted')",
            name="ck_agreements_status",
        ),
    )


class ProjectTeamMember(Base):
    """A staffing fact, not a login permission: project_role is validated against the assigned user's real
    User.role at assignment time. Soft-removed (removed_at); re-adding inserts a new row, so the unique
    index only constrains ACTIVE memberships."""

    __tablename__ = "project_team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    removed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index(
            "uq_project_team_members_one_active_per_user",
            "project_id",
            "user_id",
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
        ),
    )


class AuthorizationStatus:
    AUTHORIZED = "authorized"
    INVALIDATED = "invalidated"


class AuthorizationTransitionError(Exception):
    """Raised when something tries to move an invalidated authorization back to authorized."""


class ProjectExecutionAuthorization(Base):
    """A PM/Director decision that execution may start, bound to ONE exact quotation and the ONE exact
    Agreement revision that was executed when it was made. Append-only history: the only permitted
    status transition is authorized -> invalidated (an application rule, enforced by the before_update
    listener below and by the single invalidate_authorization() writer); re-authorizing inserts a new row.
    The partial unique index limits authorized rows per quotation to one; it does NOT by itself prevent
    flipping an invalidated row back, which is why the transition rule exists."""

    __tablename__ = "project_execution_authorizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=False)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=AuthorizationStatus.AUTHORIZED)
    authorized_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    authorized_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    invalidated_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        Index(
            "uq_execution_authorizations_one_authorized_per_quotation",
            "quotation_id",
            unique=True,
            postgresql_where=text("status = 'authorized'"),
        ),
        CheckConstraint("status IN ('authorized','invalidated')", name="ck_execution_authorizations_status"),
    )


@event.listens_for(ProjectExecutionAuthorization, "before_update")
def _refuse_reviving_an_invalidated_authorization(mapper, connection, target):
    from sqlalchemy import inspect as sa_inspect

    history = sa_inspect(target).attrs.status.history
    previously_invalidated = AuthorizationStatus.INVALIDATED in (history.deleted or ())
    if previously_invalidated and target.status == AuthorizationStatus.AUTHORIZED:
        raise AuthorizationTransitionError(
            "An invalidated execution authorization can never become authorized again; insert a new row"
        )


class MilestoneStatus:
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskStatus:
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class SiteIssueStatus:
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=MilestoneStatus.NOT_STARTED)
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_team_members.id"), nullable=True, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.NOT_STARTED)
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_milestones.id"), nullable=True)
    needs_reassignment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class ProjectSiteIssue(Base):
    __tablename__ = "project_site_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SiteIssueStatus.OPEN)
    raised_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class P5MigrationMarker(Base):
    """The durable pre-P5 eligibility boundary (Section 7): one immutable row written by the migration
    itself. A dedicated table rather than a Setting row, because Setting.changed_by_id is a NOT NULL FK
    to users (a migration has no acting user) and Settings are editable-by-versioning by design."""

    __tablename__ = "p5_migration_marker"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
