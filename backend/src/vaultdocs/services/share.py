"""
Share service functions.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.models.document import Document
from vaultdocs.models.document_share import DocumentShare
from vaultdocs.models.user import User
from vaultdocs.schemas.share import ShareCreate


async def get_share_by_id(
    db: AsyncSession,
    share_id: UUID,
) -> DocumentShare | None:
    """
    Retrieve a share by its UUID.
    """
    result = await db.execute(
        select(DocumentShare).where(DocumentShare.id == share_id),
    )
    return result.scalar_one_or_none()


async def get_share_for_document(
    db: AsyncSession,
    document_id: UUID,
    share_id: UUID,
) -> DocumentShare | None:
    """
    Retrieve a share by ID only if it belongs to the specified document.
    """
    result = await db.execute(
        select(DocumentShare).where(
            DocumentShare.id == share_id,
            DocumentShare.document_id == document_id,
        ),
    )
    return result.scalar_one_or_none()


async def list_document_shares(
    db: AsyncSession,
    document_id: UUID,
) -> list[DocumentShare]:
    """
    List all shares for a document ordered newest first.
    """
    result = await db.execute(
        select(DocumentShare)
        .where(DocumentShare.document_id == document_id)
        .order_by(DocumentShare.created_at.desc()),
    )
    return list(result.scalars().all())


async def create_share(
    db: AsyncSession,
    document: Document,
    owner_id: UUID,
    share_data: ShareCreate,
) -> DocumentShare:
    """
    Create a read-only share of a document with another registered user.

    Raises ValueError for: self-share, unknown recipient, duplicate share.
    """
    if document.owner_id != owner_id:
        raise PermissionError("Document not found.")

    email = share_data.user_email.strip().lower()

    if email == document.owner.email:
        raise ValueError("Cannot share a document with yourself.")

    result = await db.execute(
        select(User).where(User.email == email),
    )
    recipient = result.scalar_one_or_none()

    if recipient is None:
        raise ValueError("User to share with does not exist.")

    existing = await db.execute(
        select(DocumentShare).where(
            DocumentShare.document_id == document.id,
            DocumentShare.shared_with_user_id == recipient.id,
        ),
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Document is already shared with this user.")

    share = DocumentShare(
        document_id=document.id,
        shared_with_user_id=recipient.id,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share


async def revoke_share(
    db: AsyncSession,
    document: Document,
    owner_id: UUID,
    share: DocumentShare,
) -> None:
    """
    Revoke (delete) a share. Only the document owner may revoke.

    Raises PermissionError for non-owner.
    """
    if document.owner_id != owner_id:
        raise PermissionError("Document not found.")

    await db.delete(share)
    await db.commit()


async def user_can_access_document(
    db: AsyncSession,
    document: Document,
    user: User,
) -> bool:
    """
    Centralized read-access check: user is the owner or an active share recipient.
    """
    if document.owner_id == user.id:
        return True

    result = await db.execute(
        select(DocumentShare.id).where(
            DocumentShare.document_id == document.id,
            DocumentShare.shared_with_user_id == user.id,
        ),
    )
    return result.scalar_one_or_none() is not None
