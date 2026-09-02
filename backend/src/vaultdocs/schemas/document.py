"""
Document request and response schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    """
    Request body for creating a document.
    """

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the document.",
    )

    folder_id: UUID | None = Field(
        default=None,
        description="ID of the folder containing the document.",
    )


class DocumentUpdate(BaseModel):
    """
    Request body for updating a document.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated name of the document.",
    )

    folder_id: UUID | None = Field(
        default=None,
        description="Updated folder ID containing the document.",
    )


class DocumentResponse(BaseModel):
    """
    Response schema for document operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    folder_id: UUID | None
    file_path: str | None = None
    original_filename: str | None = None
    file_size: int | None = None
    content_type: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    """
    Response schema for document version operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    file_path: str
    original_filename: str
    file_size: int
    content_type: str
    created_at: datetime
