"""add skip_requests table and cost_sheets.auto_generated

Revision ID: 2d7f81a3c956
Revises: 9a2f6c4e1b87
Create Date: 2026-09-08 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2d7f81a3c956'
down_revision: Union[str, None] = '9a2f6c4e1b87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'cost_sheets',
        sa.Column('auto_generated', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('cost_sheets', 'auto_generated', server_default=None)

    op.create_table('skip_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('stage_skipped', sa.Enum('COST_SHEET', name='skip_request_stage'), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', name='skip_request_status'), nullable=False),
    sa.Column('requested_by_id', sa.UUID(), nullable=False),
    sa.Column('approved_by_id', sa.UUID(), nullable=True),
    sa.Column('resulting_cost_sheet_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['resulting_cost_sheet_id'], ['cost_sheets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('skip_requests')
    op.execute("DROP TYPE skip_request_status")
    op.execute("DROP TYPE skip_request_stage")
    op.drop_column('cost_sheets', 'auto_generated')
