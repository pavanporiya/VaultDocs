"""
Folder service functions.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.models.folder import Folder
from vaultdocs.schemas.folder import FolderCreate, FolderUpdate


async def get_folder_by_id(
    db: AsyncSession,
    folder_id: UUID,
) -> Folder | None:
    """
    Retrieve a folder by its UUID.
    """
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id),
    )
    return result.scalar_one_or_none()


async def get_user_folder_by_id(
    db: AsyncSession,
    folder_id: UUID,
    owner_id: UUID,
) -> Folder | None:
    """
    Retrieve a folder by ID only if it belongs to the specified owner.
    """
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.owner_id == owner_id,
        ),
    )
    return result.scalar_one_or_none()


async def list_user_folders(
    db: AsyncSession,
    owner_id: UUID,
) -> list[Folder]:
    """
    List all folders belonging to a given user.
    """
    result = await db.execute(
        select(Folder).where(Folder.owner_id == owner_id).order_by(Folder.created_at.asc()),
    )
    return list(result.scalars().all())


async def validate_parent_folder(
    db: AsyncSession,
    owner_id: UUID,
    parent_id: UUID,
    current_folder_id: UUID | None = None,
) -> Folder:
    """
    Validate that parent folder exists, belongs to owner, and does not create a cycle.
    """
    if current_folder_id is not None and parent_id == current_folder_id:
        raise ValueError("Folder cannot be its own parent.")

    parent = await get_folder_by_id(db, parent_id)
    if parent is None:
        raise ValueError("Parent folder not found.")

    if parent.owner_id != owner_id:
        raise ValueError("Parent folder does not belong to user.")

    # Cycle detection: ensure current_folder_id is not an ancestor of parent_id
    if current_folder_id is not None:
        curr: Folder | None = parent
        while curr is not None and curr.parent_id is not None:
            if curr.parent_id == current_folder_id:
                raise ValueError("Cannot set a descendant folder as parent.")
            curr = await get_folder_by_id(db, curr.parent_id)

    return parent


async def create_folder(
    db: AsyncSession,
    owner_id: UUID,
    folder_data: FolderCreate,
) -> Folder:
    """
    Create a new folder for a user.
    """
    name = folder_data.name.strip()
    if not name:
        raise ValueError("Folder name cannot be empty.")

    if folder_data.parent_id is not None:
        await validate_parent_folder(
            db=db,
            owner_id=owner_id,
            parent_id=folder_data.parent_id,
        )

    folder = Folder(
        name=name,
        owner_id=owner_id,
        parent_id=folder_data.parent_id,
    )

    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def update_folder(
    db: AsyncSession,
    folder: Folder,
    update_data: FolderUpdate,
) -> Folder:
    """
    Update an existing folder.
    """
    fields_set = update_data.model_dump(exclude_unset=True)

    if "name" in fields_set:
        if update_data.name is None or not update_data.name.strip():
            raise ValueError("Folder name cannot be empty.")
        folder.name = update_data.name.strip()

    if "parent_id" in fields_set:
        new_parent_id = update_data.parent_id
        if new_parent_id is not None:
            await validate_parent_folder(
                db=db,
                owner_id=folder.owner_id,
                parent_id=new_parent_id,
                current_folder_id=folder.id,
            )
        folder.parent_id = new_parent_id

    await db.commit()
    await db.refresh(folder)
    return folder


async def delete_folder(
    db: AsyncSession,
    folder: Folder,
) -> None:
    """
    Delete a folder.
    """
    await db.delete(folder)
    await db.commit()
