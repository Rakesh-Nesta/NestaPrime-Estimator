"""add fast_track_flag to quotations (M.2 rule 8)

Revision ID: b3e5c7a2d1f9
Revises: a1d9e6f4c8b2
Create Date: 2026-09-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3e5c7a2d1f9'
down_revision: Union[str, None] = 'a1d9e6f4c8b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quotations', sa.Column('fast_track_flag', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('quotations', 'fast_track_flag', server_default=None)


def downgrade() -> None:
    op.drop_column('quotations', 'fast_track_flag')
