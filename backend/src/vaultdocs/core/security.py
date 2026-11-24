"""
Security utilities for password hashing and JWT authentication.
"""

import hashlib
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from vaultdocs.core.settings import settings

# Password hashing configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """
    Hash a plain text password.
    """
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a password against its hash.
    """
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.
    """
    expire = datetime.now(UTC) + (
        expires_delta if expires_delta else timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Decode a JWT access token.
    """
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        return None


PASSWORD_RESET_TOKEN_LENGTH = 6
PASSWORD_RESET_TOKEN_CHARS = string.ascii_uppercase + string.digits


def generate_password_reset_token() -> str:
    """
    Generate a cryptographically secure 6-character uppercase alphanumeric password reset token.
    Example: 'A0B2CJ'.
    """
    return "".join(
        secrets.choice(PASSWORD_RESET_TOKEN_CHARS) for _ in range(PASSWORD_RESET_TOKEN_LENGTH)
    )


def hash_password_reset_token(token: str) -> str:
    """
    Compute a secure SHA-256 hash of a plain text reset token.
    Normalizes token to uppercase and strips whitespace.
    """
    normalized = token.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_password_reset_token_hash(plain_token: str, hashed_token: str) -> bool:
    """
    Safely compare a plain reset token against its stored hash in constant time.
    Case-insensitive: normalizes input to uppercase before hashing.
    """
    computed = hash_password_reset_token(plain_token)
    return secrets.compare_digest(computed, hashed_token)


def create_password_reset_token(
    email: str | None = None,  # noqa: ARG001
    password_hash: str | None = None,  # noqa: ARG001
    expires_delta: timedelta | None = None,  # noqa: ARG001
) -> str:
    """
    Generate a cryptographically secure 6-character alphanumeric reset token.
    Maintains compatibility with legacy caller signatures.
    """
    return generate_password_reset_token()


# -----------------------------------------------------------------------------
# Generic hashing / random token helpers (device approval flow)
# -----------------------------------------------------------------------------


def sha256_hex(value: str) -> str:
    """
    Compute a SHA-256 hex digest of a UTF-8 string.
    Used to store only hashes of device credentials and challenge ids.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_secure_token(num_bytes: int = 32) -> str:
    """
    Generate a cryptographically secure URL-safe random token.
    Default 32 bytes -> 256 bits of entropy.
    """
    return secrets.token_urlsafe(num_bytes)


def constant_time_equals(left: str, right: str) -> bool:
    """
    Compare two strings in constant time.
    """
    return secrets.compare_digest(left, right)


# -----------------------------------------------------------------------------
# OTP helpers (verification + sign-in approval codes)
# -----------------------------------------------------------------------------


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
