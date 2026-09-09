"""add accessory_catalog_items table (Part I / Module 9)

Revision ID: b3d6e0f18a2c
Revises: a2c5e814f907
Create Date: 2026-09-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3d6e0f18a2c'
down_revision: Union[str, None] = 'a2c5e814f907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accessory_catalog_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sport_id', sa.UUID(), nullable=False),
        sa.Column('item_name', sa.String(length=150), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('quantity_per_court', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['sport_id'], ['sports.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sport_id', 'item_name', name='uq_accessory_catalog_sport_item'),
    )


def downgrade() -> None:
    op.drop_table('accessory_catalog_items')
