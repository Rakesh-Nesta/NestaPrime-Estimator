"""add vehicle_classes table (Part Q.1 freight & crane)

Revision ID: d5f83c2a9b6e
Revises: c4e91b6f3a7d
Create Date: 2026-09-09 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5f83c2a9b6e'
down_revision: Union[str, None] = 'c4e91b6f3a7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'vehicle_classes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('truck_capacity_tonnes', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('rate_per_km', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_vehicle_class_key'),
    )


def downgrade() -> None:
    op.drop_table('vehicle_classes')
