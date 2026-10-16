"""
Tests for Password Reset authentication flow with simplified 6-character tokens.

Covers:
- Request reset email for registered user generates 6 uppercase alphanumeric characters
- Clear email template displaying 6-character code
- Prevent email enumeration for non-registered email
- Rate limiting on reset requests (cooldown enforcement returning 429)
- Case-insensitive token verification (lowercase input normalizes to uppercase)
- Expired token handling
- Rate limiting and invalidation on failed token attempts
- Password reset execution with new password
- Strict single-use protection (token cannot be reused after password is changed)
- Password validation (minimum length enforcement)
- Login with new password succeeds, old password fails
- SMTP delivery failure error handling
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from vaultdocs.core.security import hash_password, hash_password_reset_token
from vaultdocs.models.user import User
from vaultdocs.services.email import (
    clear_test_outbox,
    get_test_outbox,
    set_mock_smtp,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _create_test_user(
    db: AsyncSession,
    email: str = "resetuser@example.com",
    password: str = "OriginalPass123!",  # noqa: S107
) -> User:
    """Helper to create and commit a verified test user."""
    user = User(
        full_name="Reset Tester",
        email=email,
        password_hash=hash_password(password),
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _attach_reset_token(
    db: AsyncSession,
    user: User,
    token: str = "A0B2CJ",  # noqa: S107
    expires_in_seconds: int = 900,
) -> str:
    """Helper to associate a 6-character reset token with a user."""
    user.reset_token_hash = hash_password_reset_token(token)
    user.reset_token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
    user.reset_token_last_sent_at = datetime.now(UTC)
    user.reset_token_failed_attempts = 0
    await db.commit()
    await db.refresh(user)
    return token


async def test_forgot_password_sends_email_with_6char_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test requesting a password reset sends an email with a 6 uppercase alphanumeric token."""
    email = "registered@example.com"
    await _create_test_user(db_session, email=email)
    clear_test_outbox()

    response = await client.post(
        "/v1/auth/forgot-password",
        json={"email": email},
    )
    assert response.status_code == 200
    assert "instructions shortly" in response.json()["message"]

    outbox = get_test_outbox()
    assert len(outbox) == 1
    assert outbox[0]["to_email"] == email
    assert outbox[0]["type"] == "password_reset"

    token = outbox[0]["reset_token"]
    assert len(token) == 6
    assert token.isalnum()
    assert token == token.upper()
    assert f"token={token}" in outbox[0]["reset_url"]


async def test_forgot_password_rate_limiting(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test requesting password reset too quickly triggers 429 Too Many Requests cooldown."""
    email = "ratelimit_reset@example.com"
    await _create_test_user(db_session, email=email)
    clear_test_outbox()

    first_req = await client.post(
        "/v1/auth/forgot-password",
        json={"email": email},
    )
    assert first_req.status_code == 200

    # Immediate second request should be rate limited
    second_req = await client.post(
        "/v1/auth/forgot-password",
        json={"email": email},
    )
    assert second_req.status_code == 429
    assert "wait" in second_req.json()["detail"].lower()


async def test_forgot_password_nonexistent_email_no_enumeration(
    client: AsyncClient,
) -> None:
    """Test requesting reset for non-existent email returns 200 without sending email."""
    clear_test_outbox()
    response = await client.post(
        "/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200
    assert "instructions shortly" in response.json()["message"]
    assert len(get_test_outbox()) == 0


async def test_verify_reset_token_valid_case_insensitive(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test verifying a valid reset token works case-insensitively (lowercase input)."""
    email = "verifytoken@example.com"
    user = await _create_test_user(db_session, email=email)
    token = await _attach_reset_token(db_session, user, token="A0B2CJ")

    # Send lowercase version of token
    response = await client.post(
        "/v1/auth/verify-reset-token",
        json={"token": token.lower()},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["email"] == email


async def test_verify_reset_token_invalid_or_expired(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test verifying an invalid or expired reset token returns 400 or 422."""
    # Invalid length/format (fails Pydantic pattern validation)
    bad_res = await client.post(
        "/v1/auth/verify-reset-token",
        json={"token": "toolongtoken123"},
    )
    assert bad_res.status_code == 422

    # Expired token
    email = "expired@example.com"
    user = await _create_test_user(db_session, email=email)
    expired_token = await _attach_reset_token(
        db_session, user, token="EXPIRE", expires_in_seconds=-10
    )

    exp_res = await client.post(
        "/v1/auth/verify-reset-token",
        json={"token": expired_token},
    )
    assert exp_res.status_code == 400
    assert "expired" in exp_res.json()["detail"].lower()


async def test_reset_token_rate_limiting_failed_attempts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test repeated failed token attempts are rate limited and eventually invalidate the token."""
    email = "attempts@example.com"
    user = await _create_test_user(db_session, email=email)
    real_token = await _attach_reset_token(db_session, user, token="SEC123")

    # Submit incorrect tokens scoped to email
    for i in range(1, 5):
        res = await client.post(
            "/v1/auth/verify-reset-token",
            json={"token": "WRONG1", "email": email},
        )
        assert res.status_code == 400
        assert f"{5 - i} attempt(s) remaining" in res.json()["detail"]

    # 5th failed attempt should invalidate the token
    final_fail = await client.post(
        "/v1/auth/verify-reset-token",
        json={"token": "WRONG1", "email": email},
    )
    assert final_fail.status_code == 400
    assert "invalidated" in final_fail.json()["detail"].lower()

    # Even the real token should now be invalidated
    real_res = await client.post(
        "/v1/auth/verify-reset-token",
        json={"token": real_token, "email": email},
    )
    assert real_res.status_code == 400


async def test_reset_password_success_and_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test resetting password updates hash and allows login with new credentials."""
    email = "reset_success@example.com"
    old_password = "OldPassword123!"  # noqa: S105
    new_password = "BrandNewPassword123!"  # noqa: S105

    user = await _create_test_user(db_session, email=email, password=old_password)
    await _attach_reset_token(db_session, user, token="XYZ987")

    # Submit reset with lowercase token to test case normalization
    reset_res = await client.post(
        "/v1/auth/reset-password",
        json={
            "token": "xyz987",
            "new_password": new_password,
        },
    )
    assert reset_res.status_code == 200
    assert "successfully reset" in reset_res.json()["message"]

    # Verify old password no longer works
    old_login = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old_login.status_code == 401

    # Verify new password works
    new_login = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


async def test_reset_token_is_strictly_single_use(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test reset token cannot be reused after password has been changed once."""
    email = "singleuse@example.com"
    user = await _create_test_user(db_session, email=email)
    token = await _attach_reset_token(db_session, user, token="ONCE01")

    # First use succeeds
    first_use = await client.post(
        "/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPassword123!"},
    )
    assert first_use.status_code == 200

    # Second use fails because reset_token_hash was cleared
    second_use = await client.post(
        "/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPassword123!"},
    )
    assert second_use.status_code == 400
    assert "already been used" in second_use.json()["detail"].lower()


async def test_reset_password_validates_length(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test short password is rejected during reset."""
    email = "shortpass@example.com"
    user = await _create_test_user(db_session, email=email)
    token = await _attach_reset_token(db_session, user, token="SHORT1")

    response = await client.post(
        "/v1/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert response.status_code == 422  # Pydantic validation


async def test_forgot_password_smtp_failure_returns_503(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test SMTP failure during reset request returns 503."""
    email = "smtp_fail@example.com"
    await _create_test_user(db_session, email=email)

    set_mock_smtp(True, should_fail=True)
    try:
        response = await client.post(
            "/v1/auth/forgot-password",
            json={"email": email},
        )
        assert response.status_code == 503
    finally:
        set_mock_smtp(True, should_fail=False)
