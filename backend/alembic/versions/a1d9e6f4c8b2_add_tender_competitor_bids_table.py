"""add tender_competitor_bids table (Part L L1 live view)

Revision ID: a1d9e6f4c8b2
Revises: f6c3b8e1d4a7
Create Date: 2026-09-10 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1d9e6f4c8b2'
down_revision: Union[str, None] = 'f6c3b8e1d4a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tender_competitor_bids',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tender_details_id', sa.UUID(), nullable=False),
        sa.Column('bidder_name', sa.String(length=200), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('recorded_by_id', sa.UUID(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tender_details_id'], ['tender_details.id'], ),
        sa.ForeignKeyConstraint(['recorded_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('tender_competitor_bids')
