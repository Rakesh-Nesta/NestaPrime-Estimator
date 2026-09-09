"""add netting_grades table (Part E.3)

Revision ID: c4e91b6f3a7d
Revises: b3d6e0f18a2c
Create Date: 2026-09-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e91b6f3a7d'
down_revision: Union[str, None] = 'b3d6e0f18a2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'netting_grades',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('material', sa.String(length=50), nullable=False),
        sa.Column('twine', sa.String(length=30), nullable=True),
        sa.Column('mesh', sa.String(length=30), nullable=False),
        sa.Column('uv_stabilized', sa.Boolean(), nullable=True),
        sa.Column('typical_use', sa.String(length=150), nullable=False),
        sa.Column('rate_per_sqm', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_netting_grade_key'),
    )


def downgrade() -> None:
    op.drop_table('netting_grades')
