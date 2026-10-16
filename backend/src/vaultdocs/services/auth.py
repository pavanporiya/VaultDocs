"""
Authentication service with Gmail OTP email verification support.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from vaultdocs.core.security import (
    create_access_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
    verify_password_reset_token_hash,
)
from vaultdocs.core.settings import settings
from vaultdocs.models.user import User
from vaultdocs.schemas.auth import (
    LoginRequest,
    RegisterUserRequest,
    TokenResponse,
)
from vaultdocs.services.email import (
    send_password_reset_email,
    send_verification_email,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vaultdocs.schemas.user import UserUpdate


class UnverifiedUserError(ValueError):
    """Raised when an unverified user attempts to sign in."""

    def __init__(self, message: str, email: str) -> None:
        super().__init__(message)
        self.email = email


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP."""
    code = secrets.randbelow(1_000_000)
    return f"{code:06d}"


def hash_otp(otp: str) -> str:
    """Compute SHA-256 hash of plain text OTP code."""
    return hashlib.sha256(otp.strip().encode("utf-8")).hexdigest()


def verify_otp_hash(plain_otp: str, hashed_otp: str) -> bool:
    """Safely compare plain OTP against its stored SHA-256 hash in constant time."""
    computed = hash_otp(plain_otp)
    return secrets.compare_digest(computed, hashed_otp)


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    """
    Retrieve a user by email address (case-insensitive).
    """
    normalized = email.strip().lower()
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized),
    )

    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession,
    user_data: RegisterUserRequest,
) -> User:
    """
    Register a new user, generate an OTP, and deliver it via email.

    The user is initially created with is_verified = False.
    If email delivery fails, changes are rolled back so no phantom user is created.
    """
    normalized_email = user_data.email.strip().lower()
    existing_user = await get_user_by_email(
        db,
        normalized_email,
    )

    if existing_user is not None:
        raise ValueError("Email is already registered.")

    now = datetime.now(UTC)
    otp = generate_otp()
    otp_hash = hash_otp(otp)
    otp_expires = now + timedelta(minutes=settings.otp_expire_minutes)

    user = User(
        full_name=user_data.full_name,
        email=normalized_email,
        password_hash=hash_password(user_data.password),
        is_verified=False,
        otp_code_hash=otp_hash,
        otp_expires_at=otp_expires,
        otp_last_sent_at=now,
        otp_failed_attempts=0,
    )

    # Deliver verification email before committing transaction.
    # If delivery fails (e.g. SMTP down / bad credentials), transaction will be rolled back.
    send_verification_email(
        to_email=user_data.email,
        recipient_name=user_data.full_name,
        otp_code=otp,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def verify_user_otp(
    db: AsyncSession,
    email: str,
    otp_code: str,
) -> tuple[User, str]:
    """
    Verify an OTP code submitted by a user.

    Validates single-use, expiration, and rate/attempt limits.
    On success: marks account is_verified = True, clears OTP, and issues JWT token.
    """
    user = await get_user_by_email(db, email)

    if user is None:
        raise ValueError("Invalid verification request or account is already verified.")

    if user.is_verified:
        raise ValueError("Account is already verified. Please sign in.")

    if not user.otp_code_hash or not user.otp_expires_at:
        raise ValueError("No active verification code found. Please request a new code.")

    now = datetime.now(UTC)

    # Check expiration
    if now > user.otp_expires_at:
        user.otp_code_hash = None
        user.otp_expires_at = None
        await db.commit()
        raise ValueError("Verification code has expired. Please request a new code.")

    # Check attempt limits
    if user.otp_failed_attempts >= settings.otp_max_failed_attempts:
        user.otp_code_hash = None
        user.otp_expires_at = None
        await db.commit()
        raise ValueError(
            "Too many failed verification attempts. This code has been invalidated. "
            "Please request a new code."
        )

    # Compare OTP code
    if not verify_otp_hash(otp_code, user.otp_code_hash):
        user.otp_failed_attempts += 1
        remaining = max(0, settings.otp_max_failed_attempts - user.otp_failed_attempts)
        if remaining == 0:
            user.otp_code_hash = None
            user.otp_expires_at = None
            await db.commit()
            raise ValueError(
                "Too many failed verification attempts. This code has been invalidated. "
                "Please request a new code."
            )
        await db.commit()
        raise ValueError(f"Invalid verification code. {remaining} attempt(s) remaining.")

    # Verification successful: activate account and invalidate OTP
    user.is_verified = True
    user.otp_code_hash = None
    user.otp_expires_at = None
    user.otp_failed_attempts = 0

    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(subject=user.email)
    return user, access_token


async def resend_user_otp(
    db: AsyncSession,
    email: str,
) -> int:
    """
    Resend an OTP verification code.

    Enforces cooldown period and invalidates previous OTP code.
    Returns the cooldown duration in seconds.
    """
    user = await get_user_by_email(db, email)

    if user is None:
        raise ValueError("No pending registration found for this email address.")

    if user.is_verified:
        raise ValueError("Account is already verified. Please sign in.")

    now = datetime.now(UTC)

    # Enforce resend cooldown
    if user.otp_last_sent_at is not None:
        elapsed = (now - user.otp_last_sent_at).total_seconds()
        if elapsed < settings.otp_resend_cooldown_seconds:
            remaining = int(settings.otp_resend_cooldown_seconds - elapsed)
            raise ValueError(f"Please wait {remaining} second(s) before requesting another code.")

    new_otp = generate_otp()
    user.otp_code_hash = hash_otp(new_otp)
    user.otp_expires_at = now + timedelta(minutes=settings.otp_expire_minutes)
    user.otp_last_sent_at = now
    user.otp_failed_attempts = 0

    send_verification_email(
        to_email=user.email,
        recipient_name=user.full_name,
        otp_code=new_otp,
    )

    await db.commit()
    return settings.otp_resend_cooldown_seconds


async def authenticate_user(
    db: AsyncSession,
    login_data: LoginRequest,
) -> User | None:
    """
    Authenticate a user using email and password.

    Raises UnverifiedUserError if credentials are valid but the account is unverified.
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

    if not user.is_verified:
        raise UnverifiedUserError(
            "Account email is not verified. Please verify your email before signing in.",
            email=user.email,
        )

    if not user.is_active:
        raise ValueError("Account is deactivated.")

    return user


async def update_user_profile(
    db: AsyncSession,
    user: User,
    update_data: UserUpdate,
) -> User:
    """
    Update the current user's profile fields (currently full_name).

    Raises ValueError when the resulting full_name would be empty.
    """
    fields_set = update_data.model_dump(exclude_unset=True)

    if "full_name" in fields_set:
        if update_data.full_name is None or not update_data.full_name.strip():
            raise ValueError("Full name cannot be empty.")
        user.full_name = update_data.full_name.strip()

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_preferences(user: User) -> dict[str, Any]:
    """
    Return the user's stored preferences (empty dict when unset).
    """
    return dict(user.preferences) if user.preferences else {}


async def update_user_preferences(
    db: AsyncSession,
    user: User,
    preferences: dict[str, Any],
) -> dict[str, Any]:
    """
    Persist a full replacement of the user's preferences object.
    """
    user.preferences = preferences
    await db.commit()
    await db.refresh(user)
    return dict(user.preferences) if user.preferences else {}


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
        token_type="bearer",  # noqa: S106
    )


async def request_password_reset(
    db: AsyncSession,
    email: str,
) -> None:
    """
    Initiate a password reset flow for the given email address.

    Generates a secure, 6-character uppercase alphanumeric token,
    stores its secure hash, enforces rate limiting, and dispatches an email.
    If the email is not found, silently completes to avoid email enumeration.
    """
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        return

    now = datetime.now(UTC)

    # Enforce rate limiting on reset requests
    if user.reset_token_last_sent_at is not None:
        elapsed = (now - user.reset_token_last_sent_at).total_seconds()
        if elapsed < settings.password_reset_resend_cooldown_seconds:
            remaining = int(settings.password_reset_resend_cooldown_seconds - elapsed)
            raise ValueError(
                f"Please wait {remaining} second(s) before requesting another password reset."
            )

    reset_token = generate_password_reset_token()
    user.reset_token_hash = hash_password_reset_token(reset_token)
    user.reset_token_expires_at = now + timedelta(minutes=settings.password_reset_expire_minutes)
    user.reset_token_last_sent_at = now
    user.reset_token_failed_attempts = 0

    await db.commit()

    send_password_reset_email(
        to_email=user.email,
        recipient_name=user.full_name,
        reset_token=reset_token,
    )


async def verify_password_reset_token(
    db: AsyncSession,
    token: str,
    email: str | None = None,
) -> User:
    """
    Validate a 6-character password reset token.

    Checks expiration, attempt limits, and single-use status using constant-time comparison.
    Token is normalized to uppercase for case-insensitive verification.
    """
    clean_token = token.strip().upper()
    if len(clean_token) != 6 or not clean_token.isalnum():
        raise ValueError("Invalid password reset token format. Must be 6 alphanumeric characters.")

    user: User | None = None
    if email:
        user = await get_user_by_email(db, email.strip().lower())
        if user is None or not user.is_active:
            raise ValueError("Invalid password reset token or account is inactive.")
    else:
        token_hash = hash_password_reset_token(clean_token)
        user = await db.scalar(select(User).where(User.reset_token_hash == token_hash))
        if user is None or not user.is_active:
            raise ValueError("Password reset token has already been used or is invalid.")

    if not user.reset_token_hash or not user.reset_token_expires_at:
        raise ValueError("Password reset token has already been used or is invalid.")

    now = datetime.now(UTC)

    # Check expiration
    if now > user.reset_token_expires_at:
        user.reset_token_hash = None
        user.reset_token_expires_at = None
        await db.commit()
        raise ValueError("Password reset token has expired. Please request a new link.")

    # Check attempt limits
    if user.reset_token_failed_attempts >= settings.password_reset_max_failed_attempts:
        user.reset_token_hash = None
        user.reset_token_expires_at = None
        await db.commit()
        raise ValueError(
            "Too many failed attempts. This reset token has been invalidated. "
            "Please request a new token."
        )

    # Constant-time comparison
    if not verify_password_reset_token_hash(clean_token, user.reset_token_hash):
        user.reset_token_failed_attempts += 1
        remaining = max(
            0, settings.password_reset_max_failed_attempts - user.reset_token_failed_attempts
        )
        if remaining == 0:
            user.reset_token_hash = None
            user.reset_token_expires_at = None
            await db.commit()
            raise ValueError(
                "Too many failed attempts. This reset token has been invalidated. "
                "Please request a new token."
            )
        await db.commit()
        raise ValueError(f"Invalid password reset token. {remaining} attempt(s) remaining.")

    return user


async def reset_user_password(
    db: AsyncSession,
    token: str,
    new_password: str,
    email: str | None = None,
) -> User:
    """
    Reset a user's password using a valid, single-use 6-character reset token.
    Invalidates the reset token immediately upon success.
    """
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(new_password) > 128:
        raise ValueError("Password cannot exceed 128 characters.")

    user = await verify_password_reset_token(db, token=token, email=email)

    user.password_hash = hash_password(new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.reset_token_failed_attempts = 0
    user.is_verified = True

    await db.commit()
    await db.refresh(user)

    return user
