"""add field_settings table (Amendment 5 Phase 2)

Revision ID: f9a1c3b6e824
Revises: d4f2a8c916e7
Create Date: 2026-09-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f9a1c3b6e824'
down_revision: Union[str, None] = 'd4f2a8c916e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'field_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('field_key', sa.String(length=50), nullable=False),
        sa.Column(
            'state',
            sa.Enum('COMPULSORY', 'OPTIONAL', 'HIDDEN', name='field_setting_state'),
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('field_key', name='uq_field_settings_field_key'),
    )

    # Governed fields can now hold NULL -- app/api/field_settings.py's
    # FieldSetting rows (defaulting to COMPULSORY) are what actually
    # enforces "required unless a Director opts it down", not this
    # column constraint. building_status/site_condition/water_available
    # deliberately stay NOT NULL (see Section-6-phase2-specs.md for why
    # they're not governed this wave).
    op.alter_column('projects', 'soil_type', nullable=True)
    op.alter_column('projects', 'site_access', nullable=True)
    op.alter_column('projects', 'power_available', nullable=True)


def downgrade() -> None:
    op.alter_column('projects', 'power_available', nullable=False)
    op.alter_column('projects', 'site_access', nullable=False)
    op.alter_column('projects', 'soil_type', nullable=False)

    op.drop_table('field_settings')
    op.execute('DROP TYPE field_setting_state')
