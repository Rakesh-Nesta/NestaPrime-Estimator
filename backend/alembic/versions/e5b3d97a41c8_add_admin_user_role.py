"""add ADMIN to user_role (Amendment 59, Section 62)

Revision ID: e5b3d97a41c8
Revises: c37a4e8b2f19
Create Date: 2026-09-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5b3d97a41c8'
down_revision: Union[str, None] = 'c37a4e8b2f19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adding a value to an EXISTING Postgres enum needs an explicit ALTER TYPE. SQLAlchemy stores the Python
    # enum member's NAME, matching every value already in this type ('SALES', 'PM', 'DIRECTOR', ...), so the
    # new value is 'ADMIN', not the lowercase 'admin' UserRole.value. No existing row changes.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ADMIN'")


def downgrade() -> None:
    # Postgres cannot drop a single value from an enum. Leaving 'ADMIN' in the type is harmless once no row
    # uses it; if any account still has the ADMIN role, change or remove it before rolling back the code.
    pass
