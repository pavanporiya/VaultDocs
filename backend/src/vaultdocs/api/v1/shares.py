"""
Share API endpoints (owner-side management).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User
from vaultdocs.schemas.share import ShareCreate, ShareResponse
from vaultdocs.services.document import get_document_by_id
from vaultdocs.services.share import (
    create_share,
    get_share_for_document,
    list_document_shares,
    revoke_share,
)

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

    return ShareResponse.model_validate(share)


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
    return [ShareResponse.model_validate(s) for s in shares]


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
