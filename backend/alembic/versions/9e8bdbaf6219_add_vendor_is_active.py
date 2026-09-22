"""add vendor is_active flag (Amendment 34)

Revision ID: 9e8bdbaf6219
Revises: ac1785734f0f
Create Date: 2026-09-22 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9e8bdbaf6219'
down_revision: Union[str, None] = 'ac1785734f0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'vendors',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('vendors', 'is_active', server_default=None)


def downgrade() -> None:
    op.drop_column('vendors', 'is_active')
