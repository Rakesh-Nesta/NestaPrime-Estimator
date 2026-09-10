"""add message_templates table (Part O / M.7.2 rule 6)

Revision ID: e8a4d1f7c2b9
Revises: d5f83c2a9b6e
Create Date: 2026-09-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e8a4d1f7c2b9'
down_revision: Union[str, None] = 'd5f83c2a9b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'message_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'document_type',
            postgresql.ENUM(
                'COST_SHEET', 'ESTIMATE', 'QUOTATION', 'WORK_ORDER', 'TECHNICAL_BID_CHECKLIST_ITEM',
                'PRICE_REQUEST', 'SITE_SURVEY', 'ESTIMATE_OPTION',
                name='override_document_type', create_type=False,
            ),
            nullable=True,
        ),
        sa.Column('channel', postgresql.ENUM('EMAIL', 'WHATSAPP', name='message_channel', create_type=False), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column(
            'whatsapp_template_status',
            sa.Enum('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', name='whatsapp_template_status'),
            nullable=True,
        ),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'channel', name='uq_message_template_name_channel'),
    )
    op.add_column('messages', sa.Column('template_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'messages_template_id_fkey', 'messages', 'message_templates', ['template_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('messages_template_id_fkey', 'messages', type_='foreignkey')
    op.drop_column('messages', 'template_id')
    op.drop_table('message_templates')
    op.execute('DROP TYPE IF EXISTS whatsapp_template_status')
