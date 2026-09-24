"""
Share request and response schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShareCreate(BaseModel):
    """
    Request body for creating a document share.
    """

    user_email: str = Field(
        min_length=1,
        max_length=255,
        description="Email of the user to share the document with.",
    )

    download_allowed: bool = Field(
        default=True,
        description=(
            "Grant file download rights to the recipient. False creates a "
            'strictly view-only ("seen") share: safe in-browser preview only, '
            "no raw file downloads."
        ),
    )


class ShareUpdate(BaseModel):
    """
    Request body for updating an existing share's permission.
    """

    download_allowed: bool = Field(
        description=(
            "New download grant for the share. False = strictly view-only "
            '("seen"): safe in-browser preview only, no downloads.'
        ),
    )


class ShareResponse(BaseModel):
    """
    Response schema for document share operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    shared_with_user_id: UUID
    shared_with_email: str | None = Field(
        default=None,
        description="Email of the recipient user the document is shared with.",
    )
    download_allowed: bool = Field(
        default=True,
        description=(
            "Whether the recipient may download files. False = strictly "
            'view-only ("seen") share: safe preview only.'
        ),
    )
    created_at: datetime
    updated_at: datetime
