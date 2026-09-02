"""
Folder database model.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vaultdocs.db.base import Base
from vaultdocs.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from vaultdocs.models.user import User


class Folder(Base, TimestampMixin):
    """
    Folder database model representing user-owned hierarchical folders.
    """

    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationships
    owner: Mapped[User] = relationship(
        "User",
        backref="folders",
    )

    parent: Mapped[Folder | None] = relationship(
        "Folder",
        remote_side="Folder.id",
        back_populates="children",
    )

    children: Mapped[list[Folder]] = relationship(
        "Folder",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
