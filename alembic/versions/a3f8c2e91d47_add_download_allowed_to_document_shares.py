"""add download_allowed to document_shares

Revision ID: a3f8c2e91d47
Revises: f4a9c1d27e58
Create Date: 2026-09-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8c2e91d47"
down_revision: str | Sequence[str] | None = "f4a9c1d27e58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "document_shares",
        sa.Column(
            "download_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("document_shares", "download_allowed")
