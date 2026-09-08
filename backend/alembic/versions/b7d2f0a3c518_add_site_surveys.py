"""add site_surveys (Appendix C) and SITE_SURVEY doc type

Revision ID: b7d2f0a3c518
Revises: a1c4e7f92b03
Create Date: 2026-09-08 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b7d2f0a3c518'
down_revision: Union[str, None] = 'a1c4e7f92b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value -- so the new value must be 'SITE_SURVEY'.
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'SITE_SURVEY'")

    op.create_table(
        'site_surveys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'COMPLETED', name='site_survey_status'), nullable=False),
        sa.Column('client_name', sa.String(length=200), nullable=True),
        sa.Column('site_address', sa.String(length=500), nullable=True),
        sa.Column('pin_code', sa.String(length=10), nullable=True),
        sa.Column('contact_name', sa.String(length=200), nullable=True),
        sa.Column('contact_phone', sa.String(length=20), nullable=True),
        sa.Column('sports_and_count', sa.String(length=300), nullable=True),
        sa.Column('available_area_length', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('available_area_width', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('area_unit', postgresql.ENUM('FEET', 'METRES', name='unit_system', create_type=False), nullable=True),
        sa.Column('slope_or_level', postgresql.ENUM('LEVEL', 'SLOPED', 'WATER_LOGGED', name='site_condition', create_type=False), nullable=True),
        sa.Column('soil_observed', postgresql.ENUM('NORMAL', 'ROCKY', 'BLACK_COTTON', 'SANDY', 'FILLED', name='soil_type', create_type=False), nullable=True),
        sa.Column('water_logging_observed', sa.Boolean(), nullable=True),
        sa.Column('access_road_width_m', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('crane_access', sa.Boolean(), nullable=True),
        sa.Column('power_phase', sa.String(length=20), nullable=True),
        sa.Column('power_load_kw', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('water_source', sa.String(length=200), nullable=True),
        sa.Column('existing_structures_trees', sa.String(length=500), nullable=True),
        sa.Column('neighbour_constraints', sa.String(length=500), nullable=True),
        sa.Column('orientation', sa.String(length=50), nullable=True),
        sa.Column('surveyed_by_id', sa.UUID(), nullable=True),
        sa.Column('surveyed_at', sa.Date(), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['surveyed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('site_surveys')
    op.execute("DROP TYPE site_survey_status")
    # unit_system / site_condition / soil_type are pre-existing shared
    # enum types (owned by the projects table) -- not dropped here.
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- the added
    # override_document_type value is left in place on downgrade,
    # matching this codebase's accepted limitation.
