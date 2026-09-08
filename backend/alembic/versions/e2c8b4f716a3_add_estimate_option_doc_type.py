"""add ESTIMATE_OPTION doc type (M.6 product option images)

Revision ID: e2c8b4f716a3
Revises: d84f6a2e9c17
Create Date: 2026-09-08 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e2c8b4f716a3'
down_revision: Union[str, None] = 'd84f6a2e9c17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value -- so the new value must be 'ESTIMATE_OPTION'.
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'ESTIMATE_OPTION'")


def downgrade() -> None:
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- the added enum value
    # is left in place on downgrade, matching this codebase's accepted
    # limitation (see the technical_bid_checklist migration's own note).
    pass
