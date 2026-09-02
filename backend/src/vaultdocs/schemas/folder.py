"""
Folder request and response schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    """
    Request body for creating a folder.
    """

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the folder.",
    )

    parent_id: UUID | None = Field(
        default=None,
        description="ID of the parent folder for nested hierarchy.",
    )


class FolderUpdate(BaseModel):
    """
    Request body for updating a folder.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated name of the folder.",
    )

    parent_id: UUID | None = Field(
        default=None,
        description="Updated parent folder ID.",
    )


class FolderResponse(BaseModel):
    """
    Response schema for folder operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    parent_id: UUID | None
    created_at: datetime
    updated_at: datetime
