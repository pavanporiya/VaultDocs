"""
Tests for Gmail OTP authentication flow.

Covers:
- Valid registration
- Duplicate email prevention
- SMTP delivery failure safety
- Correct OTP verification
- Incorrect OTP rejection & attempt tracking
- Maximum failed attempts code invalidation
- Expired OTP rejection & invalidation
- OTP single-use protection
- Resend OTP & previous code invalidation
- Resend cooldown enforcement
- Unverified account login prevention
- Verified login JWT authentication
- Authenticated endpoint protection against unverified users
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import select

from vaultdocs.core.security import create_access_token
from vaultdocs.core.settings import settings
from vaultdocs.models.user import User
from vaultdocs.services.auth import hash_otp
from vaultdocs.services.email import (
    clear_test_outbox,
    get_test_outbox,
    send_verification_email,
    set_mock_smtp,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_valid_registration_creates_unverified_user_and_sends_otp(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test valid registration creates unverified user and sends 6-digit OTP email."""
    email = "newuser@example.com"
    response = await client.post(
        "/v1/auth/register",
        json={
            "full_name": "New User",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == "New User"
    assert data["is_verified"] is False
    assert "Verification code sent" in data["message"]

    # Verify user in database
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.is_verified is False
    assert user.otp_code_hash is not None
    assert user.otp_expires_at is not None

    # Verify email was dispatched to mock outbox
    outbox = get_test_outbox()
    assert len(outbox) == 1
    assert outbox[0]["to_email"] == email
    assert len(outbox[0]["otp_code"]) == 6
    assert outbox[0]["otp_code"].isdigit()


async def test_duplicate_email_registration_rejected(client: AsyncClient) -> None:
    """Test registering an existing email returns 400 Bad Request."""
    email = "duplicate@example.com"
    payload = {
        "full_name": "First User",
        "email": email,
        "password": "Password123!",
    }
    first_res = await client.post("/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    second_res = await client.post("/v1/auth/register", json=payload)
    assert second_res.status_code == 400
    assert "already registered" in second_res.json()["detail"].lower()


async def test_smtp_failure_rolls_back_and_does_not_create_active_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test SMTP failure during registration safely fails without creating active user."""
    email = "smtp_fail@example.com"
    set_mock_smtp(True, should_fail=True)

    try:
        response = await client.post(
            "/v1/auth/register",
            json={
                "full_name": "Failed User",
                "email": email,
                "password": "Password123!",
            },
        )
        assert response.status_code == 503
        assert "Unable to send verification email" in response.json()["detail"]

        # Ensure no user exists or appears verified
        result = await db_session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        assert user is None
    finally:
        set_mock_smtp(True, should_fail=False)


async def test_correct_otp_verification_activates_account_and_returns_jwt(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test submitting the correct OTP activates account and issues valid JWT token."""
    email = "verify_success@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Verify User",
            "email": email,
            "password": "Password123!",
        },
    )

    outbox = get_test_outbox()
    assert len(outbox) == 1
    otp = outbox[0]["otp_code"]

    verify_res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["message"] == "Account successfully verified."
    assert "access_token" in data
    assert data["user"]["is_verified"] is True

    # Verify DB state
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert user.is_verified is True
    assert user.otp_code_hash is None
    assert user.otp_expires_at is None
    assert user.otp_failed_attempts == 0


async def test_incorrect_otp_increments_attempts_and_returns_remaining(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test entering an incorrect OTP increments failed attempts and reports remaining tries."""
    email = "wrong_otp@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Wrong OTP User",
            "email": email,
            "password": "Password123!",
        },
    )

    verify_res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": "000000"},
    )
    assert verify_res.status_code == 400
    assert "Invalid verification code" in verify_res.json()["detail"]
    assert "4 attempt(s) remaining" in verify_res.json()["detail"]

    # Verify failed attempts recorded in DB
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert user.is_verified is False
    assert user.otp_failed_attempts == 1


async def test_max_failed_attempts_invalidates_otp(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test exceeding maximum failed attempts invalidates the OTP code."""
    email = "max_attempts@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Max Attempts User",
            "email": email,
            "password": "Password123!",
        },
    )

    # Submit wrong OTP until limit is reached (first 4 attempts warn remaining)
    for i in range(settings.otp_max_failed_attempts - 1):
        res = await client.post(
            "/v1/auth/verify-otp",
            json={"email": email, "otp": f"{i:06d}"},
        )
        assert res.status_code == 400
        assert "attempt(s) remaining" in res.json()["detail"]

    # 5th attempt reaches max allowed attempts and invalidates the code
    final_res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": "999999"},
    )
    assert final_res.status_code == 400
    assert "invalidated" in final_res.json()["detail"].lower()

    # Code in DB is wiped
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert user.otp_code_hash is None


async def test_expired_otp_rejected_and_invalidated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test expired OTP is rejected and invalidated."""
    email = "expired_otp@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Expired User",
            "email": email,
            "password": "Password123!",
        },
    )

    outbox = get_test_outbox()
    otp = outbox[0]["otp_code"]

    # Manually expire the OTP in the database
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.otp_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

    # Verify code is cleared
    await db_session.refresh(user)
    assert user.otp_code_hash is None


async def test_otp_single_use_cannot_be_reused(client: AsyncClient) -> None:
    """Test once an OTP is used successfully, it cannot be reused."""
    email = "single_use@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Single Use User",
            "email": email,
            "password": "Password123!",
        },
    )

    otp = get_test_outbox()[0]["otp_code"]

    first_verify = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert first_verify.status_code == 200

    # Attempt reuse
    second_verify = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert second_verify.status_code == 400
    assert "already verified" in second_verify.json()["detail"].lower()


async def test_resend_otp_invalidates_old_and_delivers_new(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test resending OTP generates new code, invalidates old code, and resets attempts."""
    email = "resend_test@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Resend User",
            "email": email,
            "password": "Password123!",
        },
    )

    first_otp = get_test_outbox()[0]["otp_code"]

    # Advance last_sent_at past cooldown so resend is permitted
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.otp_last_sent_at = datetime.now(UTC) - timedelta(seconds=70)
    user.otp_failed_attempts = 2
    await db_session.commit()

    clear_test_outbox()

    resend_res = await client.post(
        "/v1/auth/resend-otp",
        json={"email": email},
    )
    assert resend_res.status_code == 200
    assert "new verification code has been sent" in resend_res.json()["message"]

    outbox = get_test_outbox()
    assert len(outbox) == 1
    new_otp = outbox[0]["otp_code"]

    # Verify attempts were reset and old OTP is rejected
    await db_session.refresh(user)
    assert user.otp_failed_attempts == 0
    assert user.otp_code_hash == hash_otp(new_otp)

    old_res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": first_otp},
    )
    assert old_res.status_code == 400

    # New OTP verifies successfully
    new_res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": new_otp},
    )
    assert new_res.status_code == 200


async def test_resend_cooldown_enforced(
    client: AsyncClient,
) -> None:
    """Test resending immediately triggers 429 Too Many Requests."""
    email = "cooldown_test@example.com"
    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Cooldown User",
            "email": email,
            "password": "Password123!",
        },
    )

    # Immediately try to resend
    resend_res = await client.post(
        "/v1/auth/resend-otp",
        json={"email": email},
    )
    assert resend_res.status_code == 429
    assert "wait" in resend_res.json()["detail"].lower()


async def test_unverified_login_rejected_with_403(client: AsyncClient) -> None:
    """Test unverified account login attempt is rejected with 403 Forbidden."""
    email = "unverified_login@example.com"
    password = "Password123!"  # noqa: S105

    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Unverified User",
            "email": email,
            "password": password,
        },
    )

    login_res = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 403
    data = login_res.json()
    assert data["detail"]["needs_verification"] is True
    assert data["detail"]["email"] == email


async def test_verified_user_login_succeeds(client: AsyncClient) -> None:
    """Test after verification, normal login succeeds and returns valid JWT."""
    email = "verified_login@example.com"
    password = "Password123!"  # noqa: S105

    await client.post(
        "/v1/auth/register",
        json={
            "full_name": "Verified User",
            "email": email,
            "password": password,
        },
    )

    otp = get_test_outbox()[0]["otp_code"]
    verify_res = await client.post(
        "/v1/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert verify_res.status_code == 200

    login_res = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"  # noqa: S105


async def test_unverified_user_cannot_access_authenticated_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test token crafted for an unverified user cannot access protected endpoints."""
    user = User(
        full_name="Unverified Token User",
        email="unverified_token@example.com",
        password_hash="fakehash",
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(subject=user.email)
    res = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "not verified" in res.json()["detail"].lower()


def test_missing_smtp_credentials_raises_error_without_leaking_secrets() -> None:
    """Test send_verification_email raises EmailDeliveryError when credentials missing."""
    set_mock_smtp(False)  # Turn off mock to test real credentials validation
    try:
        with (
            patch.object(settings, "smtp_username", None),
            patch.object(settings, "smtp_password", None),
        ):
            try:
                send_verification_email("test@example.com", "Test User", "123456")
                raise AssertionError("Expected EmailDeliveryError")
            except Exception as exc:
                assert "SMTP credentials not configured" in str(exc)
                # Ensure no secrets or OTP are logged or leaked
                assert "123456" not in str(exc)
    finally:
        set_mock_smtp(True)
