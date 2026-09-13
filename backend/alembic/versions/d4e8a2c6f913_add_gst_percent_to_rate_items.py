"""add gst_percent override to rate_items (Note R1)

Revision ID: d4e8a2c6f913
Revises: b7d1e4a9c2f6
Create Date: 2026-09-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e8a2c6f913'
down_revision: Union[str, None] = 'b7d1e4a9c2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rate_items', sa.Column('gst_percent', sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('rate_items', 'gst_percent')
