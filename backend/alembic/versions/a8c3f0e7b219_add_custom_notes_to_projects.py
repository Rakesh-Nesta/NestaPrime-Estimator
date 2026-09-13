"""add custom_notes to projects (Amendment 5)

Revision ID: a8c3f0e7b219
Revises: e2f6c9a1d745
Create Date: 2026-09-13 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8c3f0e7b219'
down_revision: Union[str, None] = 'e2f6c9a1d745'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('custom_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'custom_notes')
