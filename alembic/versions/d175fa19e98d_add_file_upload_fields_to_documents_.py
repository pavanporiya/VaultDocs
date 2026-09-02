"""add file upload fields to documents table

Revision ID: d175fa19e98d
Revises: 734fe8dff1e1
Create Date: 2026-09-02 14:13:15.814668

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d175fa19e98d"
down_revision: str | Sequence[str] | None = "734fe8dff1e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("file_path", sa.String(length=512), nullable=True))
    op.add_column(
        "documents", sa.Column("original_filename", sa.String(length=255), nullable=True)
    )
    op.add_column("documents", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("content_type", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "content_type")
    op.drop_column("documents", "file_size")
    op.drop_column("documents", "original_filename")
    op.drop_column("documents", "file_path")
