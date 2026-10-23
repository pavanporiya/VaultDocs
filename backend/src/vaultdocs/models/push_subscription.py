"""
Web Push subscription database model.
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from vaultdocs.db.base import Base
from vaultdocs.db.mixins import TimestampMixin


class PushSubscription(Base, TimestampMixin):
    """
    A Web Push subscription for a trusted phone/PWA.

    Stores only the push service endpoint and the per-subscription encryption
    keys supplied by the browser. No device credential or user secret.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    endpoint: Mapped[str] = mapped_column(
        String(1024),
        unique=True,
        index=True,
        nullable=False,
    )

    p256dh: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    auth: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    device_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
