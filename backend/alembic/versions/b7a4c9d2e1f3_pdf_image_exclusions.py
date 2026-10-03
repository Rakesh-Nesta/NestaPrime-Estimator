"""pdf_image_exclusions: a document-specific, attributable decision to leave one stored image out of one generated PDF

Revision ID: b7a4c9d2e1f3
Revises: a5e7c2d9b413
Create Date: 2026-10-02 16:00:00.000000

Additive only (one new table). NOTE for the merge plan: P5's migration a5e7c2d9b413 also descends from 509d1202ac03, so
whichever of the two branches merges second must re-parent its down_revision onto the other (see the PR description).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7a4c9d2e1f3"
down_revision: Union[str, None] = "a5e7c2d9b413"  # re-parented onto P5's migration (merge order: P5 first)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pdf_image_exclusions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_type", sa.String(length=30), nullable=False),
        sa.Column("doc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("excluded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("excluded_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["excluded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_type", "doc_id", "attachment_id", name="uq_pdf_image_exclusion"),
    )
    op.create_index("ix_pdf_image_exclusions_doc_id", "pdf_image_exclusions", ["doc_id"])


def downgrade() -> None:
    bind = op.get_bind()
    held = bind.execute(sa.text("SELECT COUNT(*) FROM pdf_image_exclusions")).scalar()
    if held:
        raise RuntimeError(
            f"Refusing to downgrade: pdf_image_exclusions holds {held} explicit user decision(s) to leave an image out of a "
            "document; dropping the table would destroy them. Review and remove them deliberately first."
        )
    op.drop_index("ix_pdf_image_exclusions_doc_id", table_name="pdf_image_exclusions")
    op.drop_table("pdf_image_exclusions")
