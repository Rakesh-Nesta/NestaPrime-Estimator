"""add client follow-up date and note (Amendment 42)

Revision ID: a3c7e29f5d16
Revises: 9e8bdbaf6219
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c7e29f5d16'
down_revision: Union[str, None] = '9e8bdbaf6219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('next_follow_up_date', sa.Date(), nullable=True))
    op.add_column('clients', sa.Column('follow_up_note', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'follow_up_note')
    op.drop_column('clients', 'next_follow_up_date')
