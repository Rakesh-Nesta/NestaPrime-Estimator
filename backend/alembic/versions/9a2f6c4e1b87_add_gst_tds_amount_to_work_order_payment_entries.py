"""add gst_tds_amount to work_order_payment_entries

Revision ID: 9a2f6c4e1b87
Revises: 7e1a4d92c3b5
Create Date: 2026-09-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a2f6c4e1b87'
down_revision: Union[str, None] = '7e1a4d92c3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'work_order_payment_entries',
        sa.Column('gst_tds_amount', sa.Numeric(precision=14, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('work_order_payment_entries', 'gst_tds_amount')
