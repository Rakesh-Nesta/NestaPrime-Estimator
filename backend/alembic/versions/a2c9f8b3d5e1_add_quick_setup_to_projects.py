"""add quick_setup to projects (Amendment 2 blind-quoting flag)

Revision ID: a2c9f8b3d5e1
Revises: d4b8f2e6c1a3
Create Date: 2026-09-12 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2c9f8b3d5e1'
down_revision: Union[str, None] = 'd4b8f2e6c1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'projects',
        sa.Column('quick_setup', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.alter_column('projects', 'quick_setup', server_default=None)


def downgrade() -> None:
    op.drop_column('projects', 'quick_setup')
