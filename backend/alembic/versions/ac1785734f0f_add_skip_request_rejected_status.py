"""add skip request REJECTED status + rejection_reason (Amendment 33)

Revision ID: ac1785734f0f
Revises: 323ecc35b9df
Create Date: 2026-09-21 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ac1785734f0f'
down_revision: Union[str, None] = '323ecc35b9df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value -- matching the existing 'PENDING'/'APPROVED'
    # values in this type, so the new value must be 'REJECTED'.
    op.execute("ALTER TYPE skip_request_status ADD VALUE IF NOT EXISTS 'REJECTED'")
    op.add_column('skip_requests', sa.Column('rejection_reason', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('skip_requests', 'rejection_reason')
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- the added enum value
    # is left in place on downgrade, matching this codebase's accepted
    # limitation (see the technical_bid_checklist migration's own note).
