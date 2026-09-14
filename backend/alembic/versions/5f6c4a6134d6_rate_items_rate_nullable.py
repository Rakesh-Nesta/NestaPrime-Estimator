"""make rate_items.rate nullable (Amendment 11, awaiting-rate items)

Revision ID: 5f6c4a6134d6
Revises: f9a1c3b6e824
Create Date: 2026-09-14 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f6c4a6134d6'
down_revision: Union[str, None] = 'f9a1c3b6e824'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Section 10 / Amendment 11 Part A: a RateItem can now be created
    # "awaiting rate" (rate=NULL) -- present in the catalog, sport/category-
    # tagged, HSN/SAC classified, but not confirmable into an AI rate until
    # a PM/Director enters a real, quantity-backed number via POST
    # /rate-items/{id}/rate (app/api/rate_items.py enforces the rest).
    op.alter_column('rate_items', 'rate', nullable=True)


def downgrade() -> None:
    op.alter_column('rate_items', 'rate', nullable=False)
