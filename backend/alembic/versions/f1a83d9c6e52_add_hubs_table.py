"""add hubs table (Part O HUBS) and Project.hub_id

Revision ID: f1a83d9c6e52
Revises: e7c92b4a1f38
Create Date: 2026-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a83d9c6e52'
down_revision: Union[str, None] = 'e7c92b4a1f38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hubs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state_code', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.add_column('projects', sa.Column('hub_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_projects_hub_id_hubs', 'projects', 'hubs', ['hub_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_projects_hub_id_hubs', 'projects', type_='foreignkey')
    op.drop_column('projects', 'hub_id')
    op.drop_table('hubs')
