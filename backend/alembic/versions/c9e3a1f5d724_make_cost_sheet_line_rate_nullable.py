"""make cost_sheet_lines.rate nullable (K.3 Rate-blind mode)

Revision ID: c9e3a1f5d724
Revises: b7d2f0a3c518
Create Date: 2026-09-08 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e3a1f5d724'
down_revision: Union[str, None] = 'b7d2f0a3c518'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('cost_sheet_lines', 'rate', existing_type=sa.Numeric(precision=12, scale=2), nullable=True)


def downgrade() -> None:
    # Any pending (rate=None) line would violate the old NOT NULL
    # constraint -- price them at 0 rather than fail the downgrade outright.
    op.execute("UPDATE cost_sheet_lines SET rate = 0 WHERE rate IS NULL")
    op.alter_column('cost_sheet_lines', 'rate', existing_type=sa.Numeric(precision=12, scale=2), nullable=False)
