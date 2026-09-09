"""add client_rejection_reason to estimate_options (M.2 rule 9)

Revision ID: a3f7e9c1d825
Revises: e2c8b4f716a3
Create Date: 2026-09-09 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3f7e9c1d825'
down_revision: Union[str, None] = 'e2c8b4f716a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    client_rejection_reason = postgresql.ENUM(
        'PRICE', 'SCOPE', 'TIMING', 'COMPETITOR', 'OTHER', name='client_rejection_reason'
    )
    client_rejection_reason.create(op.get_bind())
    op.add_column(
        'estimate_options',
        sa.Column(
            'rejection_reason',
            postgresql.ENUM(
                'PRICE', 'SCOPE', 'TIMING', 'COMPETITOR', 'OTHER', name='client_rejection_reason', create_type=False
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('estimate_options', 'rejection_reason')
    postgresql.ENUM(name='client_rejection_reason').drop(op.get_bind())
