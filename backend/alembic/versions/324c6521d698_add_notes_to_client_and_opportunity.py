"""add notes field to clients and opportunities (Amendment 45)

Revision ID: 324c6521d698
Revises: d0d627473d3c
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '324c6521d698'
down_revision: Union[str, None] = 'd0d627473d3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('opportunities', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('opportunities', 'notes')
    op.drop_column('clients', 'notes')
