"""add company_logo table (Part O COMPANY.logo)

Revision ID: a2c5e814f907
Revises: f1a83d9c6e52
Create Date: 2026-09-10 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2c5e814f907'
down_revision: Union[str, None] = 'f1a83d9c6e52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'company_logo',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('original_sha256', sa.String(length=64), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('uploaded_by_id', sa.UUID(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('company_logo')
