"""add follow_ups and follow_up_history (WP5, correction plan, 2026-09-27)

Revision ID: b22585244a4f
Revises: b8d4e29f1a63
Create Date: 2026-09-27 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b22585244a4f'
down_revision: Union[str, None] = 'b8d4e29f1a63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_type",
            sa.Enum(
                "CLIENT", "OPPORTUNITY", "PROJECT", "SITE_SURVEY", "COST_SHEET", "ESTIMATE",
                "QUOTATION", "PRICE_REQUEST", "PAYMENT_MILESTONE", "WORK_ORDER",
                name="follow_up_entity_type",
            ),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose_key", sa.String(length=100), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("owner_explicitly_assigned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_action", sa.String(length=300), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "IN_PROGRESS", "WAITING", "COMPLETED", "CANCELLED", name="follow_up_status"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("waiting_party", sa.Enum("US", "CLIENT", "VENDOR", name="waiting_party"), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("outcome", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_follow_ups_entity", "follow_ups", ["entity_type", "entity_id"])
    op.create_index("ix_follow_ups_owner", "follow_ups", ["owner_id"])
    op.create_index("ix_follow_ups_due_date", "follow_ups", ["due_date"])
    # Prevents a duplicate OPEN automated action (same entity + purpose_key) -- NOT a
    # one-follow-up-per-record limit; a manual follow-up (purpose_key IS NULL) is never
    # deduplicated by this index. The predicate's labels are uppercase ('COMPLETED', not
    # 'completed') because that is genuinely what Postgres stores for a SQLAlchemy Enum
    # column (the Python enum's member NAME, not its .value) -- confirmed with an isolated
    # repro; using the lowercase .value here looks natural but is wrong and makes Postgres
    # refuse the CREATE INDEX outright ("invalid input value for enum follow_up_status").
    op.create_index(
        "uq_follow_ups_purpose_key_open",
        "follow_ups",
        ["entity_type", "entity_id", "purpose_key"],
        unique=True,
        postgresql_where=sa.text("purpose_key IS NOT NULL AND status NOT IN ('COMPLETED', 'CANCELLED')"),
    )

    op.create_table(
        "follow_up_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("follow_up_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("follow_ups.id"), nullable=False),
        sa.Column("changed_field", sa.String(length=30), nullable=False),
        sa.Column("old_value", sa.String(length=500), nullable=True),
        sa.Column("new_value", sa.String(length=500), nullable=True),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_follow_up_history_follow_up_id", "follow_up_history", ["follow_up_id"])


def downgrade() -> None:
    """Drops the tables outright -- safe and correct on an EMPTY schema (a fresh install
    that never went further, or a same-day revert before anyone used the feature). Once
    real FollowUp/FollowUpHistory rows exist, running this in production would destroy
    them; the correction plan's actual operational rollback is an application-code revert
    (stop routing writes through /follow-ups, read the legacy Client/Opportunity columns
    again, which this migration never touches) -- never this downgrade. See the WP5 PR
    description for a demonstration of both: this downgrade cleanly reversing an empty
    schema, and a populated one surviving a code-level revert untouched."""
    op.drop_index("ix_follow_up_history_follow_up_id", table_name="follow_up_history")
    op.drop_table("follow_up_history")

    op.drop_index("uq_follow_ups_purpose_key_open", table_name="follow_ups")
    op.drop_index("ix_follow_ups_due_date", table_name="follow_ups")
    op.drop_index("ix_follow_ups_owner", table_name="follow_ups")
    op.drop_index("ix_follow_ups_entity", table_name="follow_ups")
    op.drop_table("follow_ups")

    postgresql.ENUM(name="waiting_party").drop(op.get_bind())
    postgresql.ENUM(name="follow_up_status").drop(op.get_bind())
    postgresql.ENUM(name="follow_up_entity_type").drop(op.get_bind())
