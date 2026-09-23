"""
Share API endpoints (owner-side management).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.document_share import DocumentShare
from vaultdocs.models.user import User
from vaultdocs.schemas.share import ShareCreate, ShareResponse
from vaultdocs.services.document import get_document_by_id
from vaultdocs.services.share import (
    create_share,
    get_emails_for_users,
    get_share_for_document,
    list_document_shares,
    revoke_share,
)


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
    document = await get_document_by_id(db=db, document_id=document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
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
    document = await get_document_by_id(db=db, document_id=document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    shares = await list_document_shares(db=db, document_id=document_id)
    return await _with_recipient_emails(db, shares)


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
    document = await get_document_by_id(db=db, document_id=document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
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
