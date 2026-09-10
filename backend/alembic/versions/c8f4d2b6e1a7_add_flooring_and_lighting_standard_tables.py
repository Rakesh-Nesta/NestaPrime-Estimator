"""add flooring_guides, lighting_lux_standards, sport_pole_counts tables (gap #9)

Revision ID: c8f4d2b6e1a7
Revises: b3e5c7a2d1f9
Create Date: 2026-09-10 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c8f4d2b6e1a7'
down_revision: Union[str, None] = 'b3e5c7a2d1f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flooring_guides',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sport_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('primary_spec', sa.Text(), nullable=False),
        sa.Column('secondary_spec', sa.Text(), nullable=True),
        sa.Column('budget_spec', sa.Text(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('updated_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['sport_id'], ['sports.id']),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sport_id', name='uq_flooring_guide_sport'),
    )

    op.create_table(
        'lighting_lux_standards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('lux_practice', sa.Integer(), nullable=True),
        sa.Column('lux_match', sa.Integer(), nullable=True),
        sa.Column('lux_tournament', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', name='uq_lighting_lux_standard_category'),
    )

    op.create_table(
        'sport_pole_counts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sport_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pole_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['sport_id'], ['sports.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sport_id', name='uq_sport_pole_count_sport'),
    )


def downgrade() -> None:
    op.drop_table('sport_pole_counts')
    op.drop_table('lighting_lux_standards')
    op.drop_table('flooring_guides')
