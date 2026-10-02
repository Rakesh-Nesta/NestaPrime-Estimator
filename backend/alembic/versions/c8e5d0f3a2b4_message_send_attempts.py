"""messages: record every send attempt BEFORE the provider is contacted (request id, fingerprint, state, linked resend)

Revision ID: c8e5d0f3a2b4
Revises: b7a4c9d2e1f3
Create Date: 2026-10-02 17:00:00.000000

Additive only (nullable columns + one unique index): existing rows stay valid (request_id NULL = a legacy row whose
state is derived from its status). NOTE for the merge plan: P5's migration a5e7c2d9b413 also descends from the old head
509d1202ac03, so whichever branch merges second must re-parent onto the other (see the PR description).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c8e5d0f3a2b4"
down_revision: Union[str, None] = "b7a4c9d2e1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("request_fingerprint", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("include_document", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("messages", sa.Column("attempt_state", sa.String(length=20), nullable=True))
    op.add_column("messages", sa.Column("attempt_state_at", sa.DateTime(), nullable=True))
    op.add_column("messages", sa.Column("previous_attempt_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("messages", sa.Column("resend_confirmed_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("messages", sa.Column("resend_confirmed_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_messages_previous_attempt", "messages", "messages", ["previous_attempt_id"], ["id"])
    op.create_foreign_key("fk_messages_resend_confirmed_by", "messages", "users", ["resend_confirmed_by_id"], ["id"])
    op.create_index("uq_messages_request_id", "messages", ["request_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_messages_request_id", table_name="messages")
    op.drop_constraint("fk_messages_resend_confirmed_by", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_previous_attempt", "messages", type_="foreignkey")
    for column in (
        "resend_confirmed_at", "resend_confirmed_by_id", "previous_attempt_id", "attempt_state_at", "attempt_state",
        "include_document", "content_sha256", "request_fingerprint", "request_id",
    ):
        op.drop_column("messages", column)
