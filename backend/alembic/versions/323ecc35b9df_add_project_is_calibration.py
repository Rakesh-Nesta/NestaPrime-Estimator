"""add project is_calibration flag (Amendment 28 Part B)

Revision ID: 323ecc35b9df
Revises: b98a7f5bc39a
Create Date: 2026-09-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '323ecc35b9df'
down_revision: Union[str, None] = 'b98a7f5bc39a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'projects',
        sa.Column('is_calibration', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('projects', 'is_calibration', server_default=None)


def downgrade() -> None:
    op.drop_column('projects', 'is_calibration')
