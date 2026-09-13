"""add telegram channel + provider message ids (Amendment 8)

Revision ID: d4f2a8c916e7
Revises: f3b8d6e0c452
Create Date: 2026-09-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f2a8c916e7'
down_revision: Union[str, None] = 'f3b8d6e0c452'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE message_channel ADD VALUE IF NOT EXISTS 'TELEGRAM'")

    op.add_column('messages', sa.Column('provider_message_id', sa.String(length=100), nullable=True))

    op.add_column('clients', sa.Column('telegram_chat_id', sa.String(length=64), nullable=True))
    op.add_column(
        'clients', sa.Column('telegram_opt_in', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column('clients', 'telegram_opt_in', server_default=None)


def downgrade() -> None:
    op.drop_column('clients', 'telegram_opt_in')
    op.drop_column('clients', 'telegram_chat_id')
    op.drop_column('messages', 'provider_message_id')
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- TELEGRAM is left in
    # message_channel on downgrade, same accepted limitation as this
    # codebase's other enum-value additions (see e.g.
    # c4e1a92d7f36_add_superseded_status_to_estimate_and_quotation.py).
