"""
User API endpoints: profile preferences.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User
from vaultdocs.schemas.user import UserPreferencesResponse
from vaultdocs.services.auth import get_user_preferences, update_user_preferences

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def read_my_preferences(
    current_user: User = Depends(get_current_user),
) -> UserPreferencesResponse:
    """
    Return the current user's stored preference settings.
    """
    preferences = await get_user_preferences(current_user)
    return UserPreferencesResponse(preferences=preferences)


@router.put("/me/preferences", response_model=UserPreferencesResponse)
async def update_my_preferences(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """
    Replace the current user's preference settings with the given JSON object.
    """
    preferences = await update_user_preferences(
        db=db,
        user=current_user,
        preferences=payload,
    )
    return UserPreferencesResponse(preferences=preferences)
