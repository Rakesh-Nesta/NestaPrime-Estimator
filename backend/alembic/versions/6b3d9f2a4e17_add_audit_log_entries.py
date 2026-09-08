"""add audit_log_entries table

Revision ID: 6b3d9f2a4e17
Revises: 2d7f81a3c956
Create Date: 2026-09-08 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6b3d9f2a4e17'
down_revision: Union[str, None] = '2d7f81a3c956'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_log_entries',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('document_type', sa.String(length=50), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('field', sa.String(length=100), nullable=False),
    sa.Column('old_value', sa.String(length=500), nullable=True),
    sa.Column('new_value', sa.String(length=500), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('session_id', sa.String(length=100), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_entries_timestamp'), 'audit_log_entries', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_log_entries_document_type'), 'audit_log_entries', ['document_type'], unique=False)
    op.create_index(op.f('ix_audit_log_entries_document_id'), 'audit_log_entries', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_log_entries_document_id'), table_name='audit_log_entries')
    op.drop_index(op.f('ix_audit_log_entries_document_type'), table_name='audit_log_entries')
    op.drop_index(op.f('ix_audit_log_entries_timestamp'), table_name='audit_log_entries')
    op.drop_table('audit_log_entries')
