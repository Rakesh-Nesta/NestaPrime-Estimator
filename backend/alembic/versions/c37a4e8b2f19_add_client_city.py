"""add city to clients (Amendment 37)

Revision ID: c37a4e8b2f19
Revises: b50a7c1d9e42
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c37a4e8b2f19'
down_revision: Union[str, None] = 'b50a7c1d9e42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, and deliberately NOT backfilled from billing_address: parsing
    # free text risks silently giving a real client the wrong city.
    op.add_column('clients', sa.Column('city', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'city')
