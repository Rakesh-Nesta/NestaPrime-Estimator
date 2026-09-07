"""add project_type to projects

Revision ID: 5c1e9ec816a6
Revises: 347a45338372
Create Date: 2026-09-07 21:48:29.272275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c1e9ec816a6'
down_revision: Union[str, None] = '347a45338372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


project_type_enum = sa.Enum('NEW_BUILD', 'RESURFACING', 'REPAIR', 'SUPPLY_ONLY', name='project_type')


def upgrade() -> None:
    # unlike every prior enum in this app (always added via create_table,
    # which creates dependent types automatically), this one is added via
    # add_column on an existing table -- Alembic does not create the
    # Postgres type for that path on its own, so it's created explicitly.
    project_type_enum.create(op.get_bind(), checkfirst=True)
    # server_default backfills existing projects as new_build (B.1's own
    # default); dropped after backfill since the ORM column has no
    # server-side default.
    op.add_column(
        'projects',
        sa.Column('project_type', project_type_enum, nullable=False, server_default='NEW_BUILD'),
    )
    op.alter_column('projects', 'project_type', server_default=None)


def downgrade() -> None:
    op.drop_column('projects', 'project_type')
    project_type_enum.drop(op.get_bind(), checkfirst=True)
