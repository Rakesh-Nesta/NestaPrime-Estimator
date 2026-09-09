"""add client consent fields (M.7.2 rule 5)

Revision ID: d5a3f8c1e264
Revises: c4e1a92d7f36
Create Date: 2026-09-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5a3f8c1e264'
down_revision: Union[str, None] = 'c4e1a92d7f36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'clients',
        sa.Column('whatsapp_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'clients',
        sa.Column('email_opt_in', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column('clients', sa.Column('consent_date', sa.Date(), nullable=True))
    op.alter_column('clients', 'whatsapp_opt_in', server_default=None)
    op.alter_column('clients', 'email_opt_in', server_default=None)


def downgrade() -> None:
    op.drop_column('clients', 'consent_date')
    op.drop_column('clients', 'email_opt_in')
    op.drop_column('clients', 'whatsapp_opt_in')
