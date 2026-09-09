"""add actual_l_ft/actual_w_ft to project_sports (C.3/M.6 deviation flagging)

Revision ID: b6d1f4a08e73
Revises: a3f7e9c1d825
Create Date: 2026-09-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b6d1f4a08e73'
down_revision: Union[str, None] = 'a3f7e9c1d825'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project_sports', sa.Column('actual_l_ft', sa.Numeric(precision=6, scale=1), nullable=True))
    op.add_column('project_sports', sa.Column('actual_w_ft', sa.Numeric(precision=6, scale=1), nullable=True))


def downgrade() -> None:
    op.drop_column('project_sports', 'actual_w_ft')
    op.drop_column('project_sports', 'actual_l_ft')
