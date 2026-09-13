"""add vendor_code to vendors and products table (Amendment 7)

Revision ID: e2f6c9a1d745
Revises: d4e8a2c6f913
Create Date: 2026-09-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f6c9a1d745'
down_revision: Union[str, None] = 'd4e8a2c6f913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vendors', sa.Column('vendor_code', sa.String(length=30), nullable=True))

    op.create_table(
        'products',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('spec', sa.String(length=300), nullable=True),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('approx_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_foreign_key('fk_products_vendor_id_vendors', 'products', 'vendors', ['vendor_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_products_vendor_id_vendors', 'products', type_='foreignkey')
    op.drop_table('products')
    op.drop_column('vendors', 'vendor_code')
