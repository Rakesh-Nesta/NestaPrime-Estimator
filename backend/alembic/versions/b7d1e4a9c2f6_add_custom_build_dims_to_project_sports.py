"""add custom build dimensions to project_sports (Amendment 9)

Revision ID: b7d1e4a9c2f6
Revises: a2c9f8b3d5e1
Create Date: 2026-09-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d1e4a9c2f6'
down_revision: Union[str, None] = 'a2c9f8b3d5e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project_sports', sa.Column('custom_build_l_ft', sa.Numeric(6, 1), nullable=True))
    op.add_column('project_sports', sa.Column('custom_build_w_ft', sa.Numeric(6, 1), nullable=True))


def downgrade() -> None:
    op.drop_column('project_sports', 'custom_build_w_ft')
    op.drop_column('project_sports', 'custom_build_l_ft')
