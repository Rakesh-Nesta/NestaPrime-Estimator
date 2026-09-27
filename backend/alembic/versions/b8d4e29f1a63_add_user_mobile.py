"""add mobile to users, make email optional (Amendment 61, Section 64)

Revision ID: b8d4e29f1a63
Revises: a3f9c27d5e14
Create Date: 2026-09-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8d4e29f1a63'
down_revision: Union[str, None] = 'a3f9c27d5e14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mobile", sa.String(length=20), nullable=True))
    op.create_index("ix_users_mobile", "users", ["mobile"], unique=True)
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.create_check_constraint(
        "ck_users_email_or_mobile", "users", "email IS NOT NULL OR mobile IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_email_or_mobile", "users", type_="check")
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_users_mobile", table_name="users")
    op.drop_column("users", "mobile")
