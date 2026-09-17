"""widen settings.value and audit_log_entries old/new_value to text (Amendment 14)

Revision ID: b4f7e2a9c1d3
Revises: ecaaa65ec8d4
Create Date: 2026-09-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4f7e2a9c1d3'
down_revision: Union[str, None] = 'ecaaa65ec8d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Section 14: the Quotation's T&C clauses and warranty table are now
    # settings-driven text, well beyond the 200-char values every other
    # Setting has carried so far -- and every Setting write is itself
    # logged to the audit trail (old_value/new_value), which hit the same
    # 500-char wall. Widening (not narrowing) an existing column is a
    # safe, non-destructive change -- every value already stored still fits.
    op.alter_column('settings', 'value', existing_type=sa.String(length=200), type_=sa.Text(), existing_nullable=False)
    op.alter_column('audit_log_entries', 'old_value', existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)
    op.alter_column('audit_log_entries', 'new_value', existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column('audit_log_entries', 'new_value', existing_type=sa.Text(), type_=sa.String(length=500), existing_nullable=True)
    op.alter_column('audit_log_entries', 'old_value', existing_type=sa.Text(), type_=sa.String(length=500), existing_nullable=True)
    op.alter_column('settings', 'value', existing_type=sa.Text(), type_=sa.String(length=200), existing_nullable=False)
