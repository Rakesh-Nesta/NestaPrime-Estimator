"""add must_change_password to users

Revision ID: d4b8f2e6c1a3
Revises: c8f4d2b6e1a7
Create Date: 2026-09-10 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4b8f2e6c1a3'
down_revision: Union[str, None] = 'c8f4d2b6e1a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows backfill to False -- their real passwords were never
    # a Director-issued placeholder waiting to be changed.
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'must_change_password', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
