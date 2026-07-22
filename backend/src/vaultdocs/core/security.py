"""
Security utilities for password hashing and JWT authentication.
"""

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
