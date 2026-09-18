"""add construction_sequence_steps table (Section 18, Amendment 16 Part 2)

Revision ID: f1a8c3d97b2e
Revises: b4f7e2a9c1d3
Create Date: 2026-09-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a8c3d97b2e'
down_revision: Union[str, None] = 'b4f7e2a9c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'construction_sequence_steps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sport_id', sa.UUID(), nullable=False),
        sa.Column(
            'phase',
            sa.Enum(
                'SITE_PREP', 'SUB_BASE', 'FLOORING', 'STRUCTURE_FIXTURES', 'LIGHTING', 'ACCESSORIES_FINISHING',
                name='construction_phase',
            ),
            nullable=False,
        ),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('updated_by_id', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['sport_id'], ['sports.id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sport_id', 'phase', name='uq_construction_sequence_step_sport_phase'),
    )


def downgrade() -> None:
    op.drop_table('construction_sequence_steps')
    sa.Enum(name='construction_phase').drop(op.get_bind(), checkfirst=True)
