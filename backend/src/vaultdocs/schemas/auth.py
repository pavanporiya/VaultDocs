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

    is_verified: bool = False


class RegisterResponse(BaseModel):
    """
    Response returned on successful registration.
    """

    id: UUID
    full_name: str
    email: EmailStr
    is_active: bool
    is_verified: bool
    message: str


class VerifyOtpRequest(BaseModel):
    """
    Request body for verifying an email OTP.
    """

    email: EmailStr
    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit numeric verification code.",
    )


class VerifyOtpResponse(BaseModel):
    """
    Response returned when an OTP is successfully verified.
    """

    message: str
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    user: UserResponse


class ResendOtpRequest(BaseModel):
    """
    Request body for resending an email OTP.
    """

    email: EmailStr


class ResendOtpResponse(BaseModel):
    """
    Response returned when an OTP resend is triggered.
    """

    message: str
    email: EmailStr
    resend_cooldown_seconds: int


class ForgotPasswordRequest(BaseModel):
    """
    Request body for initiating a password reset.
    """

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """
    Response returned when a password reset is requested.
    """

    message: str


class VerifyResetTokenRequest(BaseModel):
    """
    Request body for validating a password reset token.
    """

    token: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[A-Za-z0-9]{6}$",
        description="6-character alphanumeric password reset token.",
    )
    email: EmailStr | None = Field(
        default=None,
        description="Optional registered email address for scoped validation and rate limiting.",
    )


class VerifyResetTokenResponse(BaseModel):
    """
    Response returned when a password reset token is verified.
    """

    valid: bool = True
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """
    Request body for resetting a password using a reset token.
    """

    token: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[A-Za-z0-9]{6}$",
        description="6-character alphanumeric password reset token.",
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New account password.",
    )
    email: EmailStr | None = Field(
        default=None,
        description="Optional registered email address for scoped validation and rate limiting.",
    )


class ResetPasswordResponse(BaseModel):
    """
    Response returned when a password has been successfully reset.
    """

    message: str
