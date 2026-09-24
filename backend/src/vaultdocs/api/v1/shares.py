"""
Share API endpoints (owner-side management).
"""

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.document_share import DocumentShare
from vaultdocs.models.user import User
from vaultdocs.schemas.share import ShareCreate, ShareResponse, ShareUpdate

if TYPE_CHECKING:
    from vaultdocs.models.document import Document
from vaultdocs.services.document import get_document_by_id
from vaultdocs.services.share import (
    create_share,
    get_emails_for_users,
    get_share_for_document,
    list_document_shares,
    revoke_share,
    update_share_permission,
    user_can_access_document,
)


def _raise_not_found() -> HTTPException:
    """
    Safe 404 for documents the user cannot see (never disclose existence).
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found.",
    )


async def _get_document_owner_only(
    db: AsyncSession,
    document_id: UUID,
    current_user: User,
) -> "Document":
    """
    Fetch a document and assert the requester owns it.

    Outsiders get a safe 404 (existence never disclosed); share recipients
    get a clean 403 Forbidden because they can see the document but may not
    manage its shares.
    """
    document = await get_document_by_id(db=db, document_id=document_id)
    if document is None:
        raise _raise_not_found()

    if document.owner_id != current_user.id:
        if await user_can_access_document(db=db, document=document, user=current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the document owner can manage shares.",
            )
        raise _raise_not_found()

    return document


async def _with_recipient_emails(
    db: AsyncSession,
    shares: list[DocumentShare],
) -> list[ShareResponse]:
    """
    Serialize shares, populating shared_with_email from the users table.
    """
    emails = await get_emails_for_users(
        db=db,
        user_ids=[s.shared_with_user_id for s in shares],
    )

    responses: list[ShareResponse] = []
    for share in shares:
        item = ShareResponse.model_validate(share)
        item.shared_with_email = emails.get(item.shared_with_user_id)
        responses.append(item)
    return responses


router = APIRouter(
    prefix="/documents",
    tags=["Shares"],
)


@router.post(
    "/{document_id}/shares",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_share(
    document_id: UUID,
    share_data: ShareCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareResponse:
    """
    Share a document (read-only) with another registered user. Owner only.
    """
    document = await _get_document_owner_only(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )

    try:
        share = await create_share(
            db=db,
            document=document,
            owner_id=current_user.id,
            share_data=share_data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    (response,) = await _with_recipient_emails(db, [share])
    return response


@router.get(
    "/{document_id}/shares",
    response_model=list[ShareResponse],
)
async def list_shares(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ShareResponse]:
    """
    List all shares for a document. Owner only.
    """
    await _get_document_owner_only(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )

    shares = await list_document_shares(db=db, document_id=document_id)
    return await _with_recipient_emails(db, shares)


@router.patch(
    "/{document_id}/shares/{share_id}",
    response_model=ShareResponse,
)
async def update_existing_share(
    document_id: UUID,
    share_id: UUID,
    update_data: ShareUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareResponse:
    """
    Change an existing share's permission (download grant). Owner only.

    download_allowed=false -> View Only; true -> View + Download.
    Takes effect immediately for the recipient.
    """
    document = await _get_document_owner_only(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )

    share = await get_share_for_document(
        db=db,
        document_id=document_id,
        share_id=share_id,
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found.",
        )

    updated = await update_share_permission(
        db=db,
        document=document,
        owner_id=current_user.id,
        share=share,
        download_allowed=update_data.download_allowed,
    )

    (response,) = await _with_recipient_emails(db, [updated])
    return response


@router.delete(
    "/{document_id}/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_share(
    document_id: UUID,
    share_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke a share for a document. Owner only.
    """
    document = await _get_document_owner_only(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )

    share = await get_share_for_document(
        db=db,
        document_id=document_id,
        share_id=share_id,
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found.",
        )

    await revoke_share(
        db=db,
        document=document,
        owner_id=current_user.id,
        share=share,
    )
