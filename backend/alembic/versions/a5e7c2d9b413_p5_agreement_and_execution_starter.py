"""P5: agreement and execution starter

Revision ID: a5e7c2d9b413
Revises: 509d1202ac03
Create Date: 2026-10-01 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5e7c2d9b413'
down_revision: Union[str, None] = '509d1202ac03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.dialects.postgresql.UUID(as_uuid=True)

# The six P5 tables whose contents make a downgrade destructive (contract revision 7, Section 7).
# p5_migration_marker is deliberately NOT in this list: it holds no user data, only the immutable
# deploy timestamp, and is dropped with the schema.
P5_DATA_TABLES = (
    "agreements",
    "project_execution_authorizations",
    "project_team_members",
    "project_milestones",
    "project_tasks",
    "project_site_issues",
)


def upgrade() -> None:
    # Attachments can now ride on an Agreement or a site issue. SQLAlchemy's Enum(DocumentType, ...)
    # stores the Python member's NAME on this Postgres enum (see 509d1202ac03's own comment).
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'AGREEMENT'")
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'SITE_ISSUE'")

    op.create_table(
        "agreements",
        sa.Column("id", UUID, nullable=False),
        sa.Column("quotation_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="drafted"),
        sa.Column("client_signatory_id", UUID, nullable=True),
        sa.Column("client_signatory_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("client_signatory_designation_snapshot", sa.String(length=200), nullable=True),
        sa.Column("client_signed_at", sa.DateTime(), nullable=True),
        sa.Column("nesta_signed_by_id", UUID, nullable=True),
        sa.Column("nesta_signed_at", sa.DateTime(), nullable=True),
        sa.Column("signed_document_attachment_id", UUID, nullable=True),
        sa.Column("signed_document_sha256", sa.String(length=64), nullable=True),
        sa.Column("evidence_locked_at", sa.DateTime(), nullable=True),
        sa.Column("supersedes_id", UUID, nullable=True),
        sa.Column("void_reason", sa.String(length=500), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by_id", UUID, nullable=True),
        sa.Column("created_by_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["client_signatory_id"], ["client_signatories.id"]),
        sa.ForeignKeyConstraint(["nesta_signed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["signed_document_attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["agreements.id"]),
        sa.ForeignKeyConstraint(["voided_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('drafted','client_signed','executed','superseded','voided','legacy_adopted')",
            name="ck_agreements_status",
        ),
    )
    op.create_index(
        "uq_agreements_one_current_per_quotation", "agreements", ["quotation_id"], unique=True,
        postgresql_where=sa.text("status NOT IN ('superseded', 'voided')"),
    )
    op.create_index("ix_agreements_signed_document_attachment_id", "agreements", ["signed_document_attachment_id"])

    op.create_table(
        "project_team_members",
        sa.Column("id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("project_role", sa.String(length=20), nullable=False),
        sa.Column("assigned_by_id", UUID, nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("removed_by_id", UUID, nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["removed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_project_team_members_one_active_per_user", "project_team_members", ["project_id", "user_id"],
        unique=True, postgresql_where=sa.text("removed_at IS NULL"),
    )

    op.create_table(
        "project_execution_authorizations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("quotation_id", UUID, nullable=False),
        sa.Column("agreement_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="authorized"),
        sa.Column("authorized_by_id", UUID, nullable=False),
        sa.Column("authorized_at", sa.DateTime(), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(), nullable=True),
        sa.Column("invalidated_reason", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"]),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["authorized_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('authorized','invalidated')", name="ck_execution_authorizations_status"),
    )
    op.create_index(
        "uq_execution_authorizations_one_authorized_per_quotation", "project_execution_authorizations",
        ["quotation_id"], unique=True, postgresql_where=sa.text("status = 'authorized'"),
    )

    op.create_table(
        "project_milestones",
        sa.Column("id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="not_started"),
        sa.Column("work_order_id", UUID, nullable=True),
        sa.Column("created_by_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])

    op.create_table(
        "project_tasks",
        sa.Column("id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to_id", UUID, nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="not_started"),
        sa.Column("milestone_id", UUID, nullable=True),
        sa.Column("needs_reassignment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["project_team_members.id"]),
        sa.ForeignKeyConstraint(["milestone_id"], ["project_milestones.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"])
    op.create_index("ix_project_tasks_assigned_to_id", "project_tasks", ["assigned_to_id"])

    op.create_table(
        "project_site_issues",
        sa.Column("id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=10), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("raised_by_id", UUID, nullable=False),
        sa.Column("resolved_by_id", UUID, nullable=True),
        sa.Column("resolution_reason", sa.String(length=500), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["raised_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_site_issues_project_id", "project_site_issues", ["project_id"])

    # The durable pre-P5 eligibility boundary: written once, here, never edited by any code path.
    op.create_table(
        "p5_migration_marker",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deployed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_p5_migration_marker_single_row"),
    )
    op.execute("INSERT INTO p5_migration_marker (id, deployed_at) VALUES (1, (now() AT TIME ZONE 'utc'))")


def downgrade() -> None:
    bind = op.get_bind()
    populated = {
        table: bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in P5_DATA_TABLES
    }
    # The marker is the legacy-adoption eligibility boundary and a downgrade -> upgrade cycle writes a NEW one.
    # A Work Order created while P5 was live (after the marker) was gated by P5; letting a later, newer marker
    # sweep it in as "pre-P5" would widen the boundary, so such a downgrade is refused outright. (Work Orders
    # created while P5 is DOWNGRADED run the old, ungated code and are legitimately legacy.)
    post_marker = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM work_orders WHERE created_at > "
            "COALESCE((SELECT deployed_at FROM p5_migration_marker WHERE id = 1), 'infinity'::timestamp)"
        )
    ).scalar()
    populated["work_orders_created_after_p5"] = post_marker
    populated = {table: count for table, count in populated.items() if count}
    if populated:
        raise RuntimeError(
            "Refusing to downgrade: P5 data exists and would be destroyed: "
            + ", ".join(f"{table}={count}" for table, count in populated.items())
        )
    op.drop_table("p5_migration_marker")
    op.drop_table("project_site_issues")
    op.drop_table("project_tasks")
    op.drop_table("project_milestones")
    op.drop_table("project_execution_authorizations")
    op.drop_table("project_team_members")
    op.drop_table("agreements")
    # The AGREEMENT / SITE_ISSUE values added to override_document_type are left in place: Postgres
    # cannot drop an enum value, and an unused value is harmless (same as every prior enum addition).
