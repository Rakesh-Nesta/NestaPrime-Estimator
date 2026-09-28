"""add readiness exceptions (WP7, correction plan, 2026-09-28)

Revision ID: 80c3b2fa4b57
Revises: c4a8f091e527
Create Date: 2026-09-28 17:23:43.554319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '80c3b2fa4b57'
down_revision: Union[str, None] = 'c4a8f091e527'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # WP7: the Scope readiness check passes once a Project has this set -- see
    # Project.scope_confirmed_empty_at's own docstring. Plain DateTime/UUID columns,
    # not enums, so none of the add_column-doesn't-create-an-enum-type gotcha applies.
    op.add_column('projects', sa.Column('scope_confirmed_empty_at', sa.DateTime(), nullable=True))
    op.add_column('projects', sa.Column('scope_confirmed_empty_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'projects_scope_confirmed_empty_by_id_fkey', 'projects', 'users',
        ['scope_confirmed_empty_by_id'], ['id'],
    )

    # create_table (unlike add_column) creates a referenced enum type on its own --
    # confirmed against skip_requests' own migration -- so no explicit CREATE TYPE here.
    op.create_table('readiness_exceptions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_type', sa.Enum('ESTIMATE', 'QUOTATION', name='readiness_document_type'), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('check_key', sa.Enum('SITE_SURVEY', 'SCOPE', 'SPORT', name='readiness_check_key'), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('REQUESTED', 'APPROVED', 'REJECTED', name='readiness_exception_status'), nullable=False),
    sa.Column('requested_by_id', sa.UUID(), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('approved_by_id', sa.UUID(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('rejection_reason', sa.String(length=500), nullable=True),
    sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('readiness_exceptions')
    op.execute("DROP TYPE readiness_exception_status")
    op.execute("DROP TYPE readiness_check_key")
    op.execute("DROP TYPE readiness_document_type")
    op.drop_constraint('projects_scope_confirmed_empty_by_id_fkey', 'projects', type_='foreignkey')
    op.drop_column('projects', 'scope_confirmed_empty_by_id')
    op.drop_column('projects', 'scope_confirmed_empty_at')
