"""add cover_note to quotations (Amendment 13, AI-assisted content)

Revision ID: ecaaa65ec8d4
Revises: 5f6c4a6134d6
Create Date: 2026-09-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ecaaa65ec8d4'
down_revision: Union[str, None] = '5f6c4a6134d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quotations', sa.Column('cover_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('quotations', 'cover_note')
