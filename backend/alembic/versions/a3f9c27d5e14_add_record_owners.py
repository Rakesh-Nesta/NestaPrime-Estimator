"""add owner_id to clients, projects and opportunities (Amendment 60, Section 63)

Revision ID: a3f9c27d5e14
Revises: e5b3d97a41c8
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3f9c27d5e14'
down_revision: Union[str, None] = 'e5b3d97a41c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("clients", "projects", "opportunities")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f"{table}_owner_id_fkey", table, "users", ["owner_id"], ["id"])
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])

    backfill(op.get_bind())


def backfill(bind) -> None:
    # Give each existing record an owner ONLY where the data itself says who it belongs to. Client and project
    # creation was never written to the audit log, so there is no creation record to read; the evidence that exists is
    # the Opportunity trail.
    #   opportunities: the person who created the enquiry;
    #   clients:       the owner of the earliest enquiry linked to them;
    #   projects:      the owner of the enquiry that started them, else the owner their client just received.
    # Everything else stays NULL ("unassigned") for a PM or Director to assign by hand -- nothing is guessed.
    bind.execute(sa.text("UPDATE opportunities SET owner_id = created_by_id WHERE owner_id IS NULL"))
    bind.execute(
        sa.text(
            "UPDATE clients SET owner_id = ("
            "  SELECT o.owner_id FROM opportunities o WHERE o.client_id = clients.id "
            "  ORDER BY o.created_at ASC LIMIT 1) WHERE owner_id IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE projects SET owner_id = COALESCE("
            "  (SELECT o.owner_id FROM opportunities o WHERE o.id = projects.opportunity_id),"
            "  (SELECT c.owner_id FROM clients c WHERE c.id = projects.client_id)) WHERE owner_id IS NULL"
        )
    )
    for table in ("clients", "projects", "opportunities"):
        total, owned = bind.execute(
            sa.text(f"SELECT count(*), count(owner_id) FROM {table}")
        ).one()
        print(f"[Amendment 60] {table}: {owned} of {total} given an owner from existing data, {total - owned} unassigned")




def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_constraint(f"{table}_owner_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
