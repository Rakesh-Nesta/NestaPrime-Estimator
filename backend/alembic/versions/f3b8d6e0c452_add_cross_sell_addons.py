"""add cross-sell addon catalog + estimate option addons (Amendment 3)

Revision ID: f3b8d6e0c452
Revises: a8c3f0e7b219
Create Date: 2026-09-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3b8d6e0c452'
down_revision: Union[str, None] = 'a8c3f0e7b219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cross_sell_addons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column(
            'category',
            sa.Enum('LIGHTING', 'FENCING', 'SEATING', 'AMC', 'OTHER', name='addon_category'),
            nullable=False,
        ),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('margin_percent', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('all_sports', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'cross_sell_addon_sports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('addon_id', sa.UUID(), nullable=False),
        sa.Column('sport_id', sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_foreign_key(
        'fk_cross_sell_addon_sports_addon_id', 'cross_sell_addon_sports', 'cross_sell_addons', ['addon_id'], ['id']
    )
    op.create_foreign_key(
        'fk_cross_sell_addon_sports_sport_id', 'cross_sell_addon_sports', 'sports', ['sport_id'], ['id']
    )

    op.create_table(
        'estimate_option_addons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('estimate_option_id', sa.UUID(), nullable=False),
        sa.Column('addon_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('selling_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('margin_percent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_foreign_key(
        'fk_estimate_option_addons_option_id', 'estimate_option_addons', 'estimate_options',
        ['estimate_option_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_estimate_option_addons_addon_id', 'estimate_option_addons', 'cross_sell_addons', ['addon_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_estimate_option_addons_addon_id', 'estimate_option_addons', type_='foreignkey')
    op.drop_constraint('fk_estimate_option_addons_option_id', 'estimate_option_addons', type_='foreignkey')
    op.drop_table('estimate_option_addons')

    op.drop_constraint('fk_cross_sell_addon_sports_sport_id', 'cross_sell_addon_sports', type_='foreignkey')
    op.drop_constraint('fk_cross_sell_addon_sports_addon_id', 'cross_sell_addon_sports', type_='foreignkey')
    op.drop_table('cross_sell_addon_sports')

    op.drop_table('cross_sell_addons')
    op.execute('DROP TYPE addon_category')
