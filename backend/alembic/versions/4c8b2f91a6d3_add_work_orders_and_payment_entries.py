"""add work_orders, work_order_payment_entries, and WORK_ORDER doc type

Revision ID: 4c8b2f91a6d3
Revises: 9d3a1e7c5b2f
Create Date: 2026-09-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c8b2f91a6d3'
down_revision: Union[str, None] = '9d3a1e7c5b2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Attachment.doc_type reuses the existing "override_document_type"
    # Postgres enum -- adding a value to an EXISTING type (not created via
    # create_table in this migration) needs an explicit ALTER TYPE.
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value (matching every other value already in this
    # type: 'COST_SHEET', 'ESTIMATE', 'QUOTATION') -- so the new value
    # must be 'WORK_ORDER', not the lowercase 'work_order' DocumentType's
    # own .value happens to be.
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'WORK_ORDER'")

    op.create_table('work_orders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('quotation_id', sa.UUID(), nullable=False),
    sa.Column('awarded_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.Enum('AWARDED', 'IN_PROGRESS', 'COMPLETED', name='work_order_status'), nullable=False),
    sa.Column('created_by_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['quotation_id'], ['quotations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quotation_id')
    )

    op.create_table('work_order_payment_entries',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('work_order_id', sa.UUID(), nullable=False),
    sa.Column('milestone_name', sa.String(length=200), nullable=False),
    sa.Column('amount_received', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('received_date', sa.Date(), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('created_by_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('work_order_payment_entries')
    op.drop_table('work_orders')
    op.execute("DROP TYPE work_order_status")
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- removing the
    # 'work_order' value on downgrade would require rebuilding the whole
    # enum type, which risks Attachment rows already using it. Left as-is,
    # matching the accepted (documented) limitation of additive enum
    # migrations in this codebase.
