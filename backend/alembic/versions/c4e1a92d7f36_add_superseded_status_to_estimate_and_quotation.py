"""add SUPERSEDED status to estimate/quotation (M.2 rule 4 revisions)

Revision ID: c4e1a92d7f36
Revises: b6d1f4a08e73
Create Date: 2026-09-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4e1a92d7f36'
down_revision: Union[str, None] = 'b6d1f4a08e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE estimate_status ADD VALUE IF NOT EXISTS 'SUPERSEDED'")
    op.execute("ALTER TYPE quotation_status ADD VALUE IF NOT EXISTS 'SUPERSEDED'")


def downgrade() -> None:
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- the added enum values
    # are left in place on downgrade, matching this codebase's accepted
    # limitation (see the technical_bid_checklist migration's own note).
    pass
