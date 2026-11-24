"""add login challenges and trusted devices tables

Revision ID: 9c1f7a2b5e31
Revises: e8f1b2c3d4e5
Create Date: 2026-10-17

Additive-only migration: creates two new tables for the email-OTP
sign-in approval + trusted-device flow. No existing tables, rows or
constraints are modified, so all existing users, documents, folders,
permissions and sessions are preserved. (The Web Push approval feature
was removed before this migration shipped; a push_subscriptions table
created by an earlier local run of this revision is simply left in
place — it is never dropped, keeping this migration non-destructive.)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c1f7a2b5e31"
down_revision: str | Sequence[str] | None = "e8f1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the login security tables (additive only)."""
    op.create_table(
        "trusted_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_trusted_devices_user_id"),
        "trusted_devices",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trusted_devices_device_token_hash"),
        "trusted_devices",
        ["device_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_trusted_devices_expires_at"),
        "trusted_devices",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "login_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("remember_device", sa.Boolean(), nullable=False),
        sa.Column("delivery_method", sa.String(length=16), nullable=False),
        sa.Column("device_id_hash", sa.String(length=64), nullable=True),
        sa.Column("approval_code_hash", sa.String(length=64), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code_last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code_failed_attempts", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_device_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_by_ip", sa.String(length=45), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_login_challenges_challenge_id"),
        "login_challenges",
        ["challenge_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_login_challenges_user_id"),
        "login_challenges",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_login_challenges_status"),
        "login_challenges",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_login_challenges_expires_at"),
        "login_challenges",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the login security tables (no other data touched)."""
    op.drop_index(
        op.f("ix_login_challenges_expires_at"),
        table_name="login_challenges",
    )
    op.drop_index(
        op.f("ix_login_challenges_status"),
        table_name="login_challenges",
    )
    op.drop_index(
        op.f("ix_login_challenges_user_id"),
        table_name="login_challenges",
    )
    op.drop_index(
        op.f("ix_login_challenges_challenge_id"),
        table_name="login_challenges",
    )
    op.drop_table("login_challenges")

    op.drop_index(
        op.f("ix_trusted_devices_expires_at"),
        table_name="trusted_devices",
    )
    op.drop_index(
        op.f("ix_trusted_devices_device_token_hash"),
        table_name="trusted_devices",
    )
    op.drop_index(
        op.f("ix_trusted_devices_user_id"),
        table_name="trusted_devices",
    )
    op.drop_table("trusted_devices")
