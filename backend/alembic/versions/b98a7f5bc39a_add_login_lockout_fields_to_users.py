"""add login lockout fields to users

Revision ID: b98a7f5bc39a
Revises: a7c4e9f2b615
Create Date: 2026-09-19 17:06:23.045408

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b98a7f5bc39a'
down_revision: Union[str, None] = 'a7c4e9f2b615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Amendment 18 (Section 24): existing rows backfill to 0 attempts /
    # never locked -- there's no history of failed attempts to recreate.
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('users', 'failed_login_attempts', server_default=None)
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
