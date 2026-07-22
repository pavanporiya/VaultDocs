"""
Authentication service.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from vaultdocs.models.user import User
from vaultdocs.schemas.auth import (
    LoginRequest,
    RegisterUserRequest,
    TokenResponse,
)


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    """
    Retrieve a user by email address.
    """
    result = await db.execute(
        select(User).where(User.email == email),
    )

    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    user_data: RegisterUserRequest,
) -> User:
    """
    Create a new user in the database.
    """
    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )

    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


async def register_user(
    db: AsyncSession,
    user_data: RegisterUserRequest,
) -> User:
    """
    Register a new user if the email is not already registered.
    """
    existing_user = await get_user_by_email(
        db,
        user_data.email,
    )

    if existing_user is not None:
        raise ValueError("Email is already registered.")

    return await create_user(
        db,
        user_data,
    )


async def authenticate_user(
    db: AsyncSession,
    login_data: LoginRequest,
) -> User | None:
    """
    Authenticate a user using email and password.
    """
    user = await get_user_by_email(
        db,
        login_data.email,
    )

    if user is None:
        return None

    if not verify_password(
        login_data.password,
        user.password_hash,
    ):
        return None

    return user


async def login_user(
    db: AsyncSession,
    login_data: LoginRequest,
) -> TokenResponse:
    """
    Authenticate a user and return an access token.
    """
    user = await authenticate_user(
        db,
        login_data,
    )

    if user is None:
        raise ValueError("Invalid email or password.")

    access_token = create_access_token(
        subject=user.email,
    )

    return TokenResponse(
        access_token=access_token,
    )
