"""
Folder API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User
from vaultdocs.schemas.folder import (
    FolderCreate,
    FolderResponse,
    FolderUpdate,
)
from vaultdocs.services.folder import (
    create_folder,
    delete_folder,
    get_folder_by_id,
    list_user_folders,
    update_folder,
)

router = APIRouter(
    prefix="/folders",
    tags=["Folders"],
)


@router.post(
    "",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_folder(
    folder_data: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FolderResponse:
    """
    Create a new folder for the authenticated user.
    """
    try:
        folder = await create_folder(
            db=db,
            owner_id=current_user.id,
            folder_data=folder_data,
        )
        return FolderResponse.model_validate(folder)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[FolderResponse],
)
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FolderResponse]:
    """
    List all folders owned by the authenticated user.
    """
    folders = await list_user_folders(
        db=db,
        owner_id=current_user.id,
    )
    return [FolderResponse.model_validate(f) for f in folders]


@router.get(
    "/{folder_id}",
    response_model=FolderResponse,
)
async def get_folder(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FolderResponse:
    """
    Retrieve a specific folder owned by the authenticated user.
    """
    folder = await get_folder_by_id(
        db=db,
        folder_id=folder_id,
    )
    if folder is None or folder.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )
    return FolderResponse.model_validate(folder)


@router.patch(
    "/{folder_id}",
    response_model=FolderResponse,
)
async def update_existing_folder(
    folder_id: UUID,
    update_data: FolderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FolderResponse:
    """
    Update a folder owned by the authenticated user.
    """
    folder = await get_folder_by_id(
        db=db,
        folder_id=folder_id,
    )
    if folder is None or folder.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )

    try:
        updated_folder = await update_folder(
            db=db,
            folder=folder,
            update_data=update_data,
        )
        return FolderResponse.model_validate(updated_folder)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_existing_folder(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a folder owned by the authenticated user.
    """
    folder = await get_folder_by_id(
        db=db,
        folder_id=folder_id,
    )
    if folder is None or folder.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )

    await delete_folder(
        db=db,
        folder=folder,
    )
