"""add technical_bid_checklist_items and TECHNICAL_BID_CHECKLIST_ITEM doc type

Revision ID: 7e1a4d92c3b5
Revises: 4c8b2f91a6d3
Create Date: 2026-09-08 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7e1a4d92c3b5'
down_revision: Union[str, None] = '4c8b2f91a6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value -- matching every existing value in this type
    # ('COST_SHEET', 'ESTIMATE', 'QUOTATION', 'WORK_ORDER'), so the new
    # value must be 'TECHNICAL_BID_CHECKLIST_ITEM', not the lowercase
    # DocumentType.value.
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'TECHNICAL_BID_CHECKLIST_ITEM'")

    op.create_table('technical_bid_checklist_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.Enum('GST', 'PAN', 'TURNOVER', 'PAST_WORK_CERTIFICATES', 'ISO', name='technical_bid_checklist_key'), nullable=False),
    sa.Column('confirmed', sa.Boolean(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    sa.Column('confirmed_by_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['confirmed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('technical_bid_checklist_items')
    op.execute("DROP TYPE technical_bid_checklist_key")
    # See the work_orders migration's own downgrade note: Postgres has no
    # "ALTER TYPE ... DROP VALUE", so the added enum value is left in
    # place on downgrade, matching this codebase's accepted limitation.
