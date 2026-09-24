"""add work order payment milestones and receipt-to-milestone link (Amendment 50)

Revision ID: b50a7c1d9e42
Revises: 324c6521d698
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b50a7c1d9e42'
down_revision: Union[str, None] = '324c6521d698'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'work_order_payment_milestones',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('amount_due', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column(
        'work_order_payment_entries',
        sa.Column('milestone_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'work_order_payment_entries_milestone_id_fkey',
        'work_order_payment_entries',
        'work_order_payment_milestones',
        ['milestone_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'work_order_payment_entries_milestone_id_fkey', 'work_order_payment_entries', type_='foreignkey'
    )
    op.drop_column('work_order_payment_entries', 'milestone_id')
    op.drop_table('work_order_payment_milestones')
