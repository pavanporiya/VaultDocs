"""
Login challenge database model (sign-in approval flow).
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from vaultdocs.db.base import Base
from vaultdocs.db.mixins import TimestampMixin


class LoginChallenge(Base, TimestampMixin):
    """
    A short-lived, single-use sign-in approval challenge.

    Created when credentials are valid but the device is not trusted.
    Never stores passwords, JWTs or raw device credentials.
    """

    __tablename__ = "login_challenges"

    # Challenge statuses
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    STATUS_CONSUMED = "consumed"

    # Delivery methods
    DELIVERY_EMAIL = "email"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # High-entropy (256-bit) opaque identifier given to the pending login
    # client for polling/completion. Single-use; acts as a capability only
    # for the waiting client, never authorizing anything by itself.
    challenge_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        default=STATUS_PENDING,
        index=True,
        nullable=False,
    )

    remember_device: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    delivery_method: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    # Hash of the device cookie presented at login (may reference a stale or
    # untrusted cookie). Used to prevent the initiating session approving
    # itself; never a usable credential.
    device_id_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Email fallback approval code (hash only, single use, attempt limited).
    approval_code_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    code_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    code_failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolved_by_device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    resolved_by_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
