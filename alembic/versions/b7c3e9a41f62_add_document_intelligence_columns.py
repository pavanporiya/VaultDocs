"""add document intelligence columns

Revision ID: b7c3e9a41f62
Revises: a3f8c2e91d47
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c3e9a41f62"
down_revision: str | Sequence[str] | None = "a3f8c2e91d47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Purely additive: ten nullable columns. Existing rows keep NULL
    (interpreted by the application as "never attempted") and no existing
    column, constraint, or index is touched.
    """
    op.add_column(
        "documents",
        sa.Column("extraction_status", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("extracted_char_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("tags", sa.JSON(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("summary_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("extraction_error", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "content_fingerprint")
    op.drop_column("documents", "extracted_at")
    op.drop_column("documents", "extraction_error")
    op.drop_column("documents", "summary_source")
    op.drop_column("documents", "summary")
    op.drop_column("documents", "tags")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "extracted_char_count")
    op.drop_column("documents", "extracted_text")
    op.drop_column("documents", "extraction_status")
