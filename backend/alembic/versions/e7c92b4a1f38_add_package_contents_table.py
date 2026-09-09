"""add package_contents table (Part O PACKAGES)

Revision ID: e7c92b4a1f38
Revises: d5a3f8c1e264
Create Date: 2026-09-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e7c92b4a1f38'
down_revision: Union[str, None] = 'd5a3f8c1e264'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'package_contents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sport_id', sa.UUID(), nullable=False),
        sa.Column(
            'tier',
            postgresql.ENUM('BUDGET', 'STANDARD', 'PREMIUM', name='package', create_type=False),
            nullable=False,
        ),
        sa.Column('flooring_description', sa.Text(), nullable=False),
        sa.Column('structure_description', sa.Text(), nullable=False),
        sa.Column('lighting_description', sa.Text(), nullable=False),
        sa.Column('scope_description', sa.Text(), nullable=False),
        sa.Column('warranty_years', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.UUID(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['sport_id'], ['sports.id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sport_id', 'tier', name='uq_package_content_sport_tier'),
    )


def downgrade() -> None:
    op.drop_table('package_contents')
