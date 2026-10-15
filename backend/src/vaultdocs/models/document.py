"""
Document database model.
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vaultdocs.db.base import Base
from vaultdocs.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from vaultdocs.models.document_version import DocumentVersion
    from vaultdocs.models.folder import Folder
    from vaultdocs.models.user import User


class Document(Base, TimestampMixin):
    """
    Document database model representing user-owned documents.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    file_path: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Document intelligence (extraction / tagging / summary).
    # Nullable without server defaults: NULL means "never attempted" (e.g.
    # no file uploaded yet, or a legacy row predating this feature).
    # All columns are additive and backward compatible.
    # ------------------------------------------------------------------

    extraction_status: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_char_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Which provider produced ``summary`` ("extractive", "openai_compatible").
    # Keeps generated summaries distinguishable from extracted facts.
    summary_source: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    extraction_error: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # SHA-256 of the stored file bytes; used to skip redundant re-extraction
    # (idempotency) after re-uploads of identical content.
    content_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Relationships
    owner: Mapped[User] = relationship(
        "User",
        backref="documents",
    )

    folder: Mapped[Folder | None] = relationship(
        "Folder",
        backref="documents",
    )

    # Versions are deleted with the document: passive_deletes lets the DB-level
    # ON DELETE CASCADE remove rows instead of ORM NULL-updates (which would
    # violate document_versions.document_id NOT NULL on delete).
    versions: Mapped[list[DocumentVersion]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
