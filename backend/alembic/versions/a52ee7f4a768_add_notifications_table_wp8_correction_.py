"""add notifications table (WP8, correction plan, 2026-09-29)

Revision ID: a52ee7f4a768
Revises: 80c3b2fa4b57
Create Date: 2026-09-29 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a52ee7f4a768'
down_revision: Union[str, None] = '80c3b2fa4b57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_table auto-creates the two new enum types it references (confirmed against
    # skip_requests' own migration) -- entity_type reuses the EXISTING follow_up_entity_type
    # enum type (created by FollowUp's own migration), so that one column alone needs
    # create_type=False or Postgres would try (and fail) to create a type that already exists.
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('FOLLOW_UP_REMINDER', 'FOLLOW_UP_OVERDUE_ESCALATION', 'ACCESS_MISMATCH_ESCALATION', name='notification_kind'), nullable=False),
    sa.Column('notification_date', sa.Date(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('follow_up_id', sa.UUID(), nullable=True),
    sa.Column(
        'entity_type',
        postgresql.ENUM(
            'CLIENT', 'OPPORTUNITY', 'PROJECT', 'SITE_SURVEY', 'COST_SHEET', 'ESTIMATE', 'QUOTATION',
            'PRICE_REQUEST', 'PAYMENT_MILESTONE', 'WORK_ORDER',
            name='follow_up_entity_type', create_type=False,
        ),
        nullable=True,
    ),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('email_status', sa.Enum('PENDING', 'SENT', 'FAILED', name='notification_email_status'), nullable=False),
    sa.Column('email_attempts', sa.Integer(), nullable=False),
    sa.Column('email_last_error', sa.String(length=500), nullable=True),
    sa.Column('email_sent_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['follow_up_id'], ['follow_ups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(
        'uq_notifications_recipient_follow_up_kind_date', 'notifications',
        ['user_id', 'follow_up_id', 'kind', 'notification_date'], unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_notifications_recipient_follow_up_kind_date', table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    op.execute("DROP TYPE notification_email_status")
    op.execute("DROP TYPE notification_kind")
