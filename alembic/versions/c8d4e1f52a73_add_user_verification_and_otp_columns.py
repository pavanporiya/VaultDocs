"""add user verification and otp columns

Revision ID: c8d4e1f52a73
Revises: b7c3e9a41f62
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d4e1f52a73"
down_revision: str | Sequence[str] | None = "b7c3e9a41f62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Purely additive migration: adds account verification flag and secure OTP
    storage columns to the users table. Server defaults preserve existing rows.
    """
    op.add_column(
        "users",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "otp_code_hash",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "otp_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "otp_last_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "otp_failed_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Reversibly drops the verification and OTP tracking columns.
    """
    op.drop_column("users", "otp_failed_attempts")
    op.drop_column("users", "otp_last_sent_at")
    op.drop_column("users", "otp_expires_at")
    op.drop_column("users", "otp_code_hash")
    op.drop_column("users", "is_verified")
