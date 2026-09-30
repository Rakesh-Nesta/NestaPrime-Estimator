"""P4: document library and engineer evidence

Revision ID: 509d1202ac03
Revises: 9f2c6b1e4a70
Create Date: 2026-09-30 22:31:25.439283

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '509d1202ac03'
down_revision: Union[str, None] = '9f2c6b1e4a70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# P4 contract v7, Section 3: the new project_construction_stages table's phase column is a plain
# VARCHAR whose allowed values happen to match ConstructionSequenceStep's own ConstructionPhase
# enum (app/models/construction_sequence_step.py) -- deliberately NOT a shared Postgres enum type,
# so this table's own lifecycle never depends on that catalog table's. Hardcoded here (not
# imported from app.models) per this codebase's own convention of migrations not depending on
# application code that can change shape after the migration is written.
_CONSTRUCTION_PHASES = (
    "site_prep", "sub_base", "flooring", "structure_fixtures", "lighting", "accessories_finishing",
)

_project_construction_stages = sa.table(
    "project_construction_stages",
    sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("project_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("phase", sa.String),
    sa.column("status", sa.String),
)


def upgrade() -> None:
    # P4 contract v7, Section 3: attachments can now be uploaded against a project's own stage
    # (doc_type=PROJECT_STAGE, doc_id=project_construction_stages.id), riding the same generic
    # Attachment polymorphic system every other document type already uses. SQLAlchemy's
    # Enum(DocumentType, ...) stores the Python member's NAME on this Postgres enum, not its
    # lowercase .value -- matching this codebase's own established gotcha (see 9f2c6b1e4a70's own
    # comment on the identical issue for user_role/notification_kind).
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'PROJECT_STAGE'")

    # --- Section 3: stage evidence capture ---
    op.create_table(
        "project_construction_stages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="not_started"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_submitted_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["evidence_submitted_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "phase", name="uq_project_construction_stage_project_phase"),
    )

    # --- Section 4: reliable mobile uploads ---
    op.create_table(
        "attachment_upload_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_type", sa.String(length=30), nullable=False),
        sa.Column("doc_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("declared_size", sa.Integer(), nullable=False),
        sa.Column("declared_sha256", sa.String(length=64), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="uploading"),
        sa.Column("completion_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resulting_attachment_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("temp_files_purged_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["resulting_attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "attachment_upload_chunks",
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("received_bytes", sa.Integer(), nullable=False),
        # 'pending_write' is 13 characters -- VARCHAR(12), matching an earlier miscount in the
        # contract's own wire-block, was caught only once a real database rejected the insert.
        # Widened to 20 to match this codebase's other short-status VARCHAR columns' own margin.
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_write"),
        sa.Column("claimed_attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["attachment_upload_sessions.id"]),
        sa.PrimaryKeyConstraint("session_id", "chunk_index"),
    )

    # --- Section 3 (captured_at) + Section 5 (review / marketing-reuse) columns on attachments ---
    op.add_column("attachments", sa.Column("captured_at", sa.DateTime(), nullable=True))
    op.add_column("attachments", sa.Column("captured_at_source", sa.String(length=10), nullable=True))
    op.add_column("attachments", sa.Column("review_status", sa.String(length=20), nullable=True))
    op.add_column("attachments", sa.Column("reviewed_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("attachments", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("attachments", sa.Column("marketing_reuse_approved_at", sa.DateTime(), nullable=True))
    op.add_column(
        "attachments",
        sa.Column("marketing_reuse_approved_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("attachments", sa.Column("marketing_reuse_revoked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "attachments",
        sa.Column("marketing_reuse_revoked_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("attachments", sa.Column("derived_from_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_attachments_reviewed_by_id_users", "attachments", "users", ["reviewed_by_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_attachments_marketing_reuse_approved_by_id_users",
        "attachments", "users", ["marketing_reuse_approved_by_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_attachments_marketing_reuse_revoked_by_id_users",
        "attachments", "users", ["marketing_reuse_revoked_by_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_attachments_derived_from_id_attachments", "attachments", "attachments", ["derived_from_id"], ["id"]
    )

    # --- Backfill: one project_construction_stages row per existing project per phase ---
    # Section 3: "no legacy project is left with zero stages, and no read-only request ever
    # creates a row as a side effect." Every row starts not_started, matching what a brand-new
    # project's POST /projects-seeded rows would also start as -- indistinguishable from "never
    # touched," which is exactly what the downgrade guard below relies on.
    bind = op.get_bind()
    project_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM projects")).fetchall()]
    if project_ids:
        rows = [
            {"id": uuid.uuid4(), "project_id": project_id, "phase": phase, "status": "not_started"}
            for project_id in project_ids
            for phase in _CONSTRUCTION_PHASES
        ]
        op.bulk_insert(_project_construction_stages, rows)


def downgrade() -> None:
    bind = op.get_bind()
    table_counts = {
        table: bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in ("attachment_upload_sessions", "attachment_upload_chunks")
    }
    stage_activity_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM project_construction_stages WHERE status != 'not_started'")
    ).scalar()
    column_counts = {
        "attachments.captured_at": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE captured_at IS NOT NULL")
        ).scalar(),
        "attachments.captured_at_source": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE captured_at_source IS NOT NULL")
        ).scalar(),
        "attachments.review_status": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE review_status IS NOT NULL")
        ).scalar(),
        "attachments.reviewed_by_id": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE reviewed_by_id IS NOT NULL")
        ).scalar(),
        "attachments.reviewed_at": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE reviewed_at IS NOT NULL")
        ).scalar(),
        "attachments.marketing_reuse_approved_at": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE marketing_reuse_approved_at IS NOT NULL")
        ).scalar(),
        "attachments.marketing_reuse_approved_by_id": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE marketing_reuse_approved_by_id IS NOT NULL")
        ).scalar(),
        "attachments.marketing_reuse_revoked_at": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE marketing_reuse_revoked_at IS NOT NULL")
        ).scalar(),
        "attachments.marketing_reuse_revoked_by_id": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE marketing_reuse_revoked_by_id IS NOT NULL")
        ).scalar(),
        "attachments.derived_from_id": bind.execute(
            sa.text("SELECT COUNT(*) FROM attachments WHERE derived_from_id IS NOT NULL")
        ).scalar(),
    }
    populated = (
        {f"table:{k}" for k, v in table_counts.items() if v}
        | ({"project_construction_stages (status != not_started)"} if stage_activity_count else set())
        | {f"column:{k}" for k, v in column_counts.items() if v}
    )
    if populated:
        raise RuntimeError(
            "Refusing to roll back P4 (document library and engineer evidence): real data would be "
            f"lost. Non-empty/active: {sorted(populated)}. table row counts={table_counts}, "
            f"project_construction_stages rows with real activity={stage_activity_count}, "
            f"column non-null counts={column_counts}. This migration does not drop data silently -- "
            "resolve or explicitly accept the loss before retrying."
        )

    op.drop_constraint("fk_attachments_derived_from_id_attachments", "attachments", type_="foreignkey")
    op.drop_constraint(
        "fk_attachments_marketing_reuse_revoked_by_id_users", "attachments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_attachments_marketing_reuse_approved_by_id_users", "attachments", type_="foreignkey"
    )
    op.drop_constraint("fk_attachments_reviewed_by_id_users", "attachments", type_="foreignkey")
    op.drop_column("attachments", "derived_from_id")
    op.drop_column("attachments", "marketing_reuse_revoked_by_id")
    op.drop_column("attachments", "marketing_reuse_revoked_at")
    op.drop_column("attachments", "marketing_reuse_approved_by_id")
    op.drop_column("attachments", "marketing_reuse_approved_at")
    op.drop_column("attachments", "reviewed_at")
    op.drop_column("attachments", "reviewed_by_id")
    op.drop_column("attachments", "review_status")
    op.drop_column("attachments", "captured_at_source")
    op.drop_column("attachments", "captured_at")

    op.drop_table("attachment_upload_chunks")
    op.drop_table("attachment_upload_sessions")
    op.drop_table("project_construction_stages")

    # The Postgres enum value added in upgrade() is intentionally left in place -- Postgres has
    # no DROP VALUE for enums, matching this codebase's own established precedent for the
    # identical situation (9f2c6b1e4a70 leaves MARKETING/IMPORT_* in place on downgrade too).
