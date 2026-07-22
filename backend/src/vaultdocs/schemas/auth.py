"""
Authentication request and response schemas.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterUserRequest(BaseModel):
    """
    Request body for user registration.
    """

    full_name: str = Field(
        min_length=2,
        max_length=100,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginRequest(BaseModel):
    """
    Request body for user login.
    """

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class TokenResponse(BaseModel):
    """
    JWT access token response.
    """

    access_token: str

    token_type: str = Field(
        default="bearer",
        description="OAuth2 token type.",
    )


class TokenPayload(BaseModel):
    """
    Decoded JWT payload.
    """

    sub: str

    exp: int


class UserResponse(BaseModel):
    """
    Public user information.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    full_name: str

    email: EmailStr

    is_active: bool

    is_superuser: bool
