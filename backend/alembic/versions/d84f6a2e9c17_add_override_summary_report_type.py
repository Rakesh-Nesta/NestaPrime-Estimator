"""add OVERRIDE_SUMMARY report type (Q.2 rule 2 monthly override report)

Revision ID: d84f6a2e9c17
Revises: c9e3a1f5d724
Create Date: 2026-09-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd84f6a2e9c17'
down_revision: Union[str, None] = 'c9e3a1f5d724'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value -- matching 'PIPELINE'/'MARGIN', so the new
    # value must be 'OVERRIDE_SUMMARY', not 'override_summary'.
    op.execute("ALTER TYPE report_type ADD VALUE IF NOT EXISTS 'OVERRIDE_SUMMARY'")


def downgrade() -> None:
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- the added enum value
    # is left in place on downgrade, matching this codebase's accepted
    # limitation (see the technical_bid_checklist migration's own note).
    pass
