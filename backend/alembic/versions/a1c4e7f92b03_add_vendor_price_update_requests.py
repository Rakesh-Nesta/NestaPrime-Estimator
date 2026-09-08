"""add vendor price-update requests (M.7.3) and vendor consent fields

Revision ID: a1c4e7f92b03
Revises: 6b3d9f2a4e17
Create Date: 2026-09-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c4e7f92b03'
down_revision: Union[str, None] = '6b3d9f2a4e17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's default Enum column stores the Python enum member's
    # NAME, not its .value -- matching every existing value in this type,
    # so the new value must be 'PRICE_REQUEST', not 'price_request'.
    op.execute("ALTER TYPE override_document_type ADD VALUE IF NOT EXISTS 'PRICE_REQUEST'")

    op.add_column('vendors', sa.Column('whatsapp_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('vendors', sa.Column('email_opt_in', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('vendors', sa.Column('consent_date', sa.Date(), nullable=True))
    op.alter_column('vendors', 'whatsapp_opt_in', server_default=None)
    op.alter_column('vendors', 'email_opt_in', server_default=None)

    op.create_table(
        'price_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('requested_by_id', sa.UUID(), nullable=False),
        sa.Column('required_by', sa.Date(), nullable=True),
        sa.Column('requested_validity_days', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'REPLIED', 'CLOSED', name='price_request_status'), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'price_request_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('price_request_id', sa.UUID(), nullable=False),
        sa.Column('rate_item_id', sa.UUID(), nullable=False),
        sa.Column('spec_override', sa.String(length=300), nullable=True),
        sa.Column('quantity_band', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['price_request_id'], ['price_requests.id'], ),
        sa.ForeignKeyConstraint(['rate_item_id'], ['rate_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'price_request_vendors',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('price_request_id', sa.UUID(), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['price_request_id'], ['price_requests.id'], ),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'vendor_replies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('price_request_id', sa.UUID(), nullable=False),
        sa.Column('price_request_item_id', sa.UUID(), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.Column('raw_reply_text', sa.String(length=1000), nullable=False),
        sa.Column('parsed_rate', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('parsed_unit', sa.String(length=20), nullable=True),
        sa.Column('parsed_gst_basis', sa.Enum('INCLUSIVE', 'EXCLUSIVE', name='gst_basis'), nullable=True),
        sa.Column('parsed_validity_days', sa.Integer(), nullable=True),
        sa.Column('attachment_id', sa.UUID(), nullable=True),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('confirmed_by_id', sa.UUID(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'applied_as',
            sa.Enum('MASTER', 'COST_SHEET_LINE', 'BOTH', name='price_request_apply_target'),
            nullable=True,
        ),
        sa.Column('created_by_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['price_request_id'], ['price_requests.id'], ),
        sa.ForeignKeyConstraint(['price_request_item_id'], ['price_request_items.id'], ),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ),
        sa.ForeignKeyConstraint(['confirmed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('vendor_replies', 'confirmed', server_default=None)


def downgrade() -> None:
    op.drop_table('vendor_replies')
    op.drop_table('price_request_vendors')
    op.drop_table('price_request_items')
    op.drop_table('price_requests')
    op.execute("DROP TYPE price_request_apply_target")
    op.execute("DROP TYPE gst_basis")
    op.execute("DROP TYPE price_request_status")

    op.drop_column('vendors', 'consent_date')
    op.drop_column('vendors', 'email_opt_in')
    op.drop_column('vendors', 'whatsapp_opt_in')
    # Postgres has no "ALTER TYPE ... DROP VALUE" -- the added enum value
    # is left in place on downgrade, matching this codebase's accepted
    # limitation (see the technical_bid_checklist migration's own note).
