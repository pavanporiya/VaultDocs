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


class ShareResponse(BaseModel):
    """
    Response schema for document share operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    shared_with_user_id: UUID
    created_at: datetime
    updated_at: datetime
