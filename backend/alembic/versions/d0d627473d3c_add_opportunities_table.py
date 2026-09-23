"""add opportunities table and project opportunity_id (Amendment 44)

Revision ID: d0d627473d3c
Revises: a3c7e29f5d16
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd0d627473d3c'
down_revision: Union[str, None] = 'a3c7e29f5d16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'opportunities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('lead_name', sa.String(length=255), nullable=False),
        sa.Column('lead_phone', sa.String(length=20), nullable=True),
        sa.Column('lead_email', sa.String(length=255), nullable=True),
        sa.Column(
            'stage',
            sa.Enum('NEW', 'CONTACTED', 'QUALIFIED', 'WON', 'LOST', name='opportunity_stage'),
            nullable=False,
        ),
        sa.Column('lost_reason', sa.String(length=500), nullable=True),
        sa.Column('next_follow_up_date', sa.Date(), nullable=True),
        sa.Column('follow_up_note', sa.String(length=200), nullable=True),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
    )
    op.add_column('projects', sa.Column('opportunity_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'projects_opportunity_id_fkey', 'projects', 'opportunities', ['opportunity_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('projects_opportunity_id_fkey', 'projects', type_='foreignkey')
    op.drop_column('projects', 'opportunity_id')
    op.drop_table('opportunities')
    op.execute('DROP TYPE IF EXISTS opportunity_stage')
