"""make projects.water_available nullable (Section 22, Amendment 5 field-settings)

Revision ID: a7c4e9f2b615
Revises: f1a8c3d97b2e
Create Date: 2026-09-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c4e9f2b615'
down_revision: Union[str, None] = 'f1a8c3d97b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # water_available joins soil_type/site_access/power_available as a
    # governed field (GOVERNED_FIELD_KEYS in app/api/field_settings.py) --
    # a FieldSetting row (defaulting to COMPULSORY) is what actually
    # enforces "required unless a Director opts it down", not this column
    # constraint, same pattern f9a1c3b6e824 already established for the
    # other three.
    op.alter_column('projects', 'water_available', nullable=True)


def downgrade() -> None:
    op.alter_column('projects', 'water_available', nullable=False)
