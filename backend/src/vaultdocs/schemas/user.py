"""
User profile and preferences request/response schemas.
"""

from typing import Any

from pydantic import BaseModel, Field


class UserUpdate(BaseModel):
    """
    Request body for updating the current user's profile.
    """

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Updated full name of the user.",
    )


class UserPreferencesResponse(BaseModel):
    """
    Response schema for user preferences (free-form JSON object).
    """

    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Stored preference settings for the current user.",
    )
