"""add project phase (WP6, correction plan, 2026-09-28)

Revision ID: c4a8f091e527
Revises: b22585244a4f
Create Date: 2026-09-28 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c4a8f091e527'
down_revision: Union[str, None] = 'b22585244a4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # add_column, unlike create_table, does not create a referenced enum type on its own
    # (confirmed this session against WP5's own migration) -- create it explicitly first,
    # then reference it with create_type=False so the column definition below doesn't
    # try to create it again.
    op.execute("CREATE TYPE project_phase AS ENUM ('PRESALES', 'CONFIRMED', 'ABANDONED')")
    op.add_column(
        "projects",
        sa.Column(
            "phase",
            postgresql.ENUM("PRESALES", "CONFIRMED", "ABANDONED", name="project_phase", create_type=False),
            nullable=False,
            server_default="PRESALES",
        ),
    )
    # WP6: "Start Project" used to require a Won Opportunity, so every existing
    # opportunity-linked project was already commercially accepted -- backfill those to
    # CONFIRMED. Everything else (no opportunity link, or linked to a not-yet-Won one)
    # gets the column's own PRESALES default, already applied by ADD COLUMN above; this
    # is pre-launch, so there is no real transaction history to reconcile more precisely
    # than that (see the correction plan's own pre-launch reframing).
    op.execute(
        """
        UPDATE projects SET phase = 'CONFIRMED'
        WHERE opportunity_id IN (SELECT id FROM opportunities WHERE stage = 'WON')
        """
    )


def downgrade() -> None:
    op.drop_column("projects", "phase")
    op.execute("DROP TYPE project_phase")
