"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User
from vaultdocs.schemas.auth import (
    LoginRequest,
    RegisterUserRequest,
    TokenResponse,
    UserResponse,
)
from vaultdocs.services.auth import (
    login_user,
    register_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: RegisterUserRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Register a new user.
    """
    try:
        user = await register_user(
            db=db,
            user_data=user_data,
        )

        return UserResponse.model_validate(user)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user and return a JWT access token.
    """
    try:
        return await login_user(
            db=db,
            login_data=login_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Return the currently authenticated user.
    """
    return UserResponse.model_validate(current_user)
