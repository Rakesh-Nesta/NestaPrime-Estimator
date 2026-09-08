"""add sport_margin_policies table

Revision ID: 9d3a1e7c5b2f
Revises: 5c1e9ec816a6
Create Date: 2026-09-08 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9d3a1e7c5b2f'
down_revision: Union[str, None] = '5c1e9ec816a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sport_margin_policies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('sport_id', sa.UUID(), nullable=False),
    sa.Column('floor_margin_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['sport_id'], ['sports.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sport_id')
    )


def downgrade() -> None:
    op.drop_table('sport_margin_policies')
