"""
DocumentShare database model.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from vaultdocs.db.base import Base
from vaultdocs.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from vaultdocs.models.document import Document
    from vaultdocs.models.user import User


class DocumentShare(Base, TimestampMixin):
    """
    Document share linking a document to a recipient user.

    Grants the recipient read-only access to the shared document.
    """

    __tablename__ = "document_shares"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "shared_with_user_id",
            name="uq_document_shares_doc_id_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    shared_with_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    # passive_deletes on the Document.shares side lets the DB-level
    # ON DELETE CASCADE remove shares instead of NULLing the FK.
    document: Mapped[Document] = relationship(
        "Document",
        backref=backref("shares", passive_deletes=True),
    )

    shared_with_user: Mapped[User] = relationship(
        "User",
        backref=backref("document_shares", passive_deletes=True),
    )
