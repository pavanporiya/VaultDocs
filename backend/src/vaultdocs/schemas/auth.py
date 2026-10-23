"""
Authentication request and response schemas.
"""

from datetime import datetime
from typing import Literal
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

    remember_device: bool = Field(
        default=False,
        description=(
            "Remember this device for 30 days after a successful sign-in "
            "approval. Unchecked by default; approval is never granted "
            "automatically unless explicitly requested."
        ),
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

    device_remembered: bool = Field(
        default=False,
        description="True when this device was trusted for 30 days.",
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

# ---------------------------------------------------------------------------
# Device approval / trusted device / push subscription schemas
# ---------------------------------------------------------------------------


class ApprovalRequiredResponse(BaseModel):
    """Response returned when a sign-in requires device approval."""

    approval_required: bool = True

    challenge_id: str = Field(
        description="Opaque, single-use sign-in approval challenge id.",
    )

    delivery: Literal["push", "email"] = Field(
        description="Approval channel in use: phone push or email code.",
    )

    message: str

    expires_in_seconds: int

    resend_cooldown_seconds: int


class ChallengeStatusResponse(BaseModel):
    """Sanitized status of a pending sign-in approval challenge."""

    status: Literal[
        "pending",
        "approved",
        "denied",
        "expired",
        "cancelled",
        "consumed",
    ]

    expires_in_seconds: int


class CompleteChallengeRequest(BaseModel):
    """Request body for completing a sign-in approval challenge."""

    approval_code: str | None = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="Email fallback approval code (when no phone is registered).",
    )

    device_name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional friendly name for the device being trusted.",
    )


class ChallengeActionResponse(BaseModel):
    """Response returned after approving/denying/cancelling a challenge."""

    status: str

    message: str


class ResendChallengeResponse(BaseModel):
    """Response returned after re-dispatching an approval prompt."""

    message: str

    delivery: Literal["push", "email"]

    resend_cooldown_seconds: int


class TrustedDeviceResponse(BaseModel):
    """Public representation of a trusted device."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    device_name: str | None = None

    user_agent: str | None = None

    created_at: datetime

    last_used_at: datetime | None = None

    expires_at: datetime

    revoked_at: datetime | None = None

    is_current: bool = False


class TrustedDeviceListResponse(BaseModel):
    """List of the current user's trusted devices."""

    devices: list[TrustedDeviceResponse]


class PushKeys(BaseModel):
    """Browser-provided Web Push encryption keys."""

    p256dh: str = Field(
        min_length=10,
        max_length=128,
    )

    auth: str = Field(
        min_length=10,
        max_length=64,
    )


class PushSubscriptionRequest(BaseModel):
    """Request body for registering a Web Push subscription."""

    endpoint: str = Field(
        min_length=1,
        max_length=1024,
    )

    keys: PushKeys

    device_name: str | None = Field(
        default=None,
        max_length=100,
    )


class PushSubscriptionResponse(BaseModel):
    """Public representation of a push subscription (no encryption keys)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    endpoint: str

    device_name: str | None = None

    created_at: datetime

    expires_at: datetime

    last_success_at: datetime | None = None


class PushSubscriptionListResponse(BaseModel):
    """List of the current user's push subscriptions."""

    subscriptions: list[PushSubscriptionResponse]


class VapidKeyResponse(BaseModel):
    """VAPID public key discovery response."""

    enabled: bool

    public_key: str | None = None

