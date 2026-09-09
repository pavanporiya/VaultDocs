"""create document shares table

Revision ID: 1cbbd132f60c
Revises: 39f5f8971368
Create Date: 2026-09-09 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1cbbd132f60c"
down_revision: str | Sequence[str] | None = "39f5f8971368"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document_shares",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("shared_with_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shared_with_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "shared_with_user_id",
            name="uq_document_shares_doc_id_user_id",
        ),
    )
    op.create_index(
        op.f("ix_document_shares_document_id"),
        "document_shares",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_shares_shared_with_user_id"),
        "document_shares",
        ["shared_with_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_document_shares_shared_with_user_id"),
        table_name="document_shares",
    )
    op.drop_index(
        op.f("ix_document_shares_document_id"),
        table_name="document_shares",
    )
    op.drop_table("document_shares")
