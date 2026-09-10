"""add gst_mode to quotations (Part L Price basis toggle)

Revision ID: f6c3b8e1d4a7
Revises: e8a4d1f7c2b9
Create Date: 2026-09-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6c3b8e1d4a7'
down_revision: Union[str, None] = 'e8a4d1f7c2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    gst_mode_enum = sa.Enum('EXCLUSIVE', 'INCLUSIVE', name='gst_mode')
    gst_mode_enum.create(op.get_bind())
    op.add_column(
        'quotations',
        sa.Column('gst_mode', gst_mode_enum, nullable=False, server_default='EXCLUSIVE'),
    )
    op.alter_column('quotations', 'gst_mode', server_default=None)


def downgrade() -> None:
    op.drop_column('quotations', 'gst_mode')
    sa.Enum(name='gst_mode').drop(op.get_bind())
