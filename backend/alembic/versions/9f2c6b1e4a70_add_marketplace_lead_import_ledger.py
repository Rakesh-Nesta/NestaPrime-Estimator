"""add marketplace lead import ledger, rate gate, pull checkpoint (P3, 2026-09-30)

Revision ID: 9f2c6b1e4a70
Revises: c1a4f7b92d63
Create Date: 2026-09-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9f2c6b1e4a70'
down_revision: Union[str, None] = 'c1a4f7b92d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P3 contract (revision 4), Section 2. Adding a value to an EXISTING Postgres enum needs an
    # explicit ALTER TYPE -- SQLAlchemy stores the Python enum member's NAME, matching every
    # value already in this type, so the new values are 'MARKETING'/'IMPORT_LEAD_ASSIGNED'/
    # 'IMPORT_KEY_EXPIRED', not the lowercase .value strings (same gotcha as e5b3d97a41c8's own
    # ADMIN-role addition). No existing row changes.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'MARKETING'")
    op.execute("ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'IMPORT_LEAD_ASSIGNED'")
    op.execute("ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'IMPORT_KEY_EXPIRED'")

    op.create_table(
        'marketplace_lead_imports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('account_id', sa.String(length=100), nullable=False),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('enquiry_time', sa.DateTime(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('received_via', sa.String(length=10), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=True),
        sa.Column('sender_company', sa.String(length=200), nullable=True),
        sa.Column('sender_address', sa.String(length=500), nullable=True),
        sa.Column('sender_city', sa.String(length=100), nullable=True),
        sa.Column('sender_state', sa.String(length=100), nullable=True),
        sa.Column('sender_pincode', sa.String(length=10), nullable=True),
        sa.Column('sender_country_iso', sa.String(length=5), nullable=True),
        sa.Column('query_type', sa.String(length=5), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('opportunity_id', sa.UUID(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('manually_retried_at', sa.DateTime(), nullable=True),
        sa.Column('manually_retried_by_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
        sa.ForeignKeyConstraint(['manually_retried_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'account_id', 'external_id', name='uq_marketplace_lead_imports_identity'),
    )

    op.create_table(
        'marketplace_lead_import_duplicate_deliveries',
        sa.Column('ledger_row_id', sa.UUID(), nullable=False),
        sa.Column('delivery_count', sa.Integer(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ledger_row_id'], ['marketplace_lead_imports.id'], ),
        sa.PrimaryKeyConstraint('ledger_row_id'),
    )

    op.create_table(
        'marketplace_api_rate_gates',
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('last_call_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('platform'),
    )

    op.create_table(
        'marketplace_pull_checkpoints',
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('last_captured_end_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('platform'),
    )


def downgrade() -> None:
    # P3 contract, same refuse-on-populated-data discipline as P2's own migration (Section 0).
    # The ledger table is the only one that can ever hold real, worth-protecting data -- the rate
    # gate and checkpoint tables hold only machine-written operational state with no independent
    # value once the ledger itself is gone, so they are not separately guarded here.
    bind = op.get_bind()
    row_count = bind.execute(sa.text("SELECT COUNT(*) FROM marketplace_lead_imports")).scalar()
    if row_count:
        raise RuntimeError(
            "Refusing to roll back the P3 import ledger: real data would be lost. "
            f"marketplace_lead_imports has {row_count} row(s). "
            "This migration does not drop data silently -- resolve or explicitly accept the loss before retrying."
        )

    op.drop_table('marketplace_pull_checkpoints')
    op.drop_table('marketplace_api_rate_gates')
    op.drop_table('marketplace_lead_import_duplicate_deliveries')
    op.drop_table('marketplace_lead_imports')
    # Postgres cannot drop a single value from an enum -- same accepted limitation as
    # e5b3d97a41c8's own ADMIN-role addition. Harmless once nothing uses these values.
