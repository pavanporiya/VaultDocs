"""add password reset token columns to users

Revision ID: e8f1b2c3d4e5
Revises: c8d4e1f52a73
Create Date: 2026-10-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f1b2c3d4e5"
down_revision: str | Sequence[str] | None = "c8d4e1f52a73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Purely additive migration: adds reset token hash, expiration, last sent,
    and failed attempt tracking columns to the users table.
    """
    op.add_column(
        "users",
        sa.Column(
            "reset_token_hash",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reset_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reset_token_last_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reset_token_failed_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "reset_token_failed_attempts")
    op.drop_column("users", "reset_token_last_sent_at")
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
