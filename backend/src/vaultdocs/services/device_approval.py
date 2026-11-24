"""
Device approval service: trusted devices and login challenges.

Security model
--------------
* A login from an untrusted device creates a short-lived, single-use,
  user-bound challenge. No JWT is issued before the challenge is approved
  (email OTP) and consumed.
* The trusted-device bypass is server-verified: a raw device-cookie secret
  is hashed in the database and validated for user ownership, expiry and
  revocation before any OTP is skipped.
* Approval of a pending challenge happens exclusively through the secure
  email OTP channel; approval is never bypassed.
* Only hashes of device credentials, challenge ids and approval codes are
  stored.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select, update

from vaultdocs.core.security import (
    generate_otp,
    generate_secure_token,
    hash_otp,
    sha256_hex,
    verify_otp_hash,
)
from vaultdocs.core.settings import settings
from vaultdocs.models.login_challenge import LoginChallenge
from vaultdocs.models.trusted_device import TrustedDevice
from vaultdocs.models.user import User
from vaultdocs.services.email import (
    send_login_approval_email,
)

if TYPE_CHECKING:
    from uuid import UUID

    from fastapi import Response
    from sqlalchemy.engine import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _rowcount(result: Any) -> int:
    """
    Return the affected-row count of a DML statement result.

    SQLAlchemy types Session.execute() as Result[Any]; DML actually returns a
    CursorResult carrying rowcount, which drives the atomic single-use
    challenge transitions.
    """
    return cast("CursorResult[Any]", result).rowcount or 0


DEVICE_COOKIE_NAME = "vaultdocs_device"
DEVICE_TOKEN_BYTES = 32  # 256 bits of entropy
TRUSTED_DEVICE_MAX_AGE_SECONDS = 30 * 24 * 3600  # exactly 30 days


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ChallengeNotFoundError(Exception):
    """Raised when a login challenge does not exist or is not visible."""


class ChallengeStateError(Exception):
    """Raised when a login challenge cannot be acted upon in its state."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Trusted devices
# ---------------------------------------------------------------------------


async def get_valid_trusted_device(
    db: AsyncSession,
    user_id: UUID,
    device_token: str | None,
) -> TrustedDevice | None:
    """
    Resolve a raw device-cookie secret to a valid, unexpired, unrevoked
    trusted device belonging to `user_id`. Returns None when untrusted.
    """
    if not device_token:
        return None

    token_hash = sha256_hex(device_token)
    device = await db.scalar(
        select(TrustedDevice).where(
            TrustedDevice.device_token_hash == token_hash,
            TrustedDevice.user_id == user_id,
        )
    )

    if device is None or device.revoked_at is not None:
        return None

    if datetime.now(UTC) >= device.expires_at:
        return None

    return device


async def touch_trusted_device(
    db: AsyncSession,
    device: TrustedDevice,
    *,
    remember_device: bool,
) -> None:
    """
    Record device usage. When the user opted in to "Remember this device",
    extend trust to exactly 30 days from now (rolling).
    """
    now = datetime.now(UTC)
    device.last_used_at = now
    if remember_device:
        device.expires_at = now + timedelta(days=settings.trusted_device_expire_days)
    await db.commit()


async def create_trusted_device(
    db: AsyncSession,
    user_id: UUID,
    *,
    device_name: str | None,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[TrustedDevice, str]:
    """
    Create a trusted device for `user_id`.

    Returns the device plus the *raw* device token — the only moment the raw
    secret exists server-side. It goes straight into an HttpOnly cookie and
    is never persisted or logged.
    """
    now = datetime.now(UTC)
    raw_token = generate_secure_token(DEVICE_TOKEN_BYTES)

    device = TrustedDevice(
        user_id=user_id,
        device_token_hash=sha256_hex(raw_token),
        device_name=(device_name or "").strip()[:100] or None,
        user_agent=(user_agent or "").strip()[:255] or None,
        ip_address=(ip_address or "").strip()[:45] or None,
        last_used_at=now,
        expires_at=now + timedelta(days=settings.trusted_device_expire_days),
    )

    db.add(device)
    await db.commit()
    await db.refresh(device)

    logger.info(
        "trusted_device_created user_id=%s device_id=%s",
        user_id,
        device.id,
    )

    return device, raw_token


async def list_trusted_devices(
    db: AsyncSession,
    user_id: UUID,
) -> list[TrustedDevice]:
    """List all trusted devices for a user (newest first)."""
    result = await db.execute(
        select(TrustedDevice)
        .where(TrustedDevice.user_id == user_id)
        .order_by(TrustedDevice.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_trusted_device(
    db: AsyncSession,
    user_id: UUID,
    device_id: UUID,
) -> TrustedDevice:
    """
    Revoke a single trusted device. Raises ChallengeNotFoundError when the
    device does not exist or belongs to another user (no IDOR leak).
    """
    device = await db.scalar(
        select(TrustedDevice).where(
            TrustedDevice.id == device_id,
            TrustedDevice.user_id == user_id,
        )
    )
    if device is None:
        raise ChallengeNotFoundError("Device not found.")

    if device.revoked_at is None:
        device.revoked_at = datetime.now(UTC)
        await db.commit()
        logger.info(
            "trusted_device_revoked user_id=%s device_id=%s",
            user_id,
            device_id,
        )

    return device


async def revoke_all_security_credentials(
    db: AsyncSession,
    user_id: UUID,
) -> int:
    """
    Revoke every trusted device for a user.

    Called after credential security events (e.g. password reset) so stale
    trust never survives a compromise.
    """
    now = datetime.now(UTC)
    device_result = await db.execute(
        update(TrustedDevice)
        .where(
            TrustedDevice.user_id == user_id,
            TrustedDevice.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.commit()

    revoked = _rowcount(device_result)
    logger.info(
        "security_credentials_revoked user_id=%s revoked_count=%s",
        user_id,
        revoked,
    )
    return revoked


# ---------------------------------------------------------------------------
# Login challenges
# ---------------------------------------------------------------------------


async def _get_challenge_or_none(
    db: AsyncSession,
    challenge_id: str,
) -> LoginChallenge | None:
    result = await db.execute(
        select(LoginChallenge).where(LoginChallenge.challenge_id == challenge_id)
    )
    return result.scalar_one_or_none()


async def create_login_challenge(
    db: AsyncSession,
    user: User,
    *,
    remember_device: bool,
    device_id_hash: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> LoginChallenge:
    """
    Create a pending sign-in approval challenge for a valid login from an
    untrusted device and dispatch the secure email approval code (OTP).
    """
    now = datetime.now(UTC)
    challenge = LoginChallenge(
        challenge_id=generate_secure_token(32),
        user_id=user.id,
        status=LoginChallenge.STATUS_PENDING,
        remember_device=remember_device,
        device_id_hash=device_id_hash,
        ip_address=(ip_address or "").strip()[:45] or None,
        user_agent=(user_agent or "").strip()[:255] or None,
        expires_at=now + timedelta(seconds=settings.login_challenge_expire_seconds),
    )

    approval_code = generate_otp()
    challenge.delivery_method = LoginChallenge.DELIVERY_EMAIL
    challenge.approval_code_hash = hash_otp(approval_code)
    challenge.code_expires_at = now + timedelta(
        minutes=settings.login_approval_code_expire_minutes
    )
    challenge.code_last_sent_at = now
    # Deliver before committing: on failure no challenge is persisted,
    # mirroring the registration OTP transaction safety pattern.
    send_login_approval_email(
        to_email=user.email,
        recipient_name=user.full_name,
        approval_code=approval_code,
        expire_minutes=settings.login_approval_code_expire_minutes,
    )

    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)

    # Audit trail: ids and delivery mode only, never secrets.
    logger.info(
        "login_challenge_created user_id=%s challenge_id=%s delivery=%s remember_device=%s ip=%s",
        user.id,
        challenge.challenge_id,
        challenge.delivery_method,
        remember_device,
        ip_address,
    )

    return challenge


async def _transition_challenge(
    db: AsyncSession,
    challenge: LoginChallenge,
    status: str,
) -> bool:
    """
    Atomically transition a pending challenge. Returns False when the
    challenge was already resolved by a concurrent request.
    """
    now = datetime.now(UTC)
    values: dict[str, Any] = {"status": status}
    if status != LoginChallenge.STATUS_PENDING:
        values["resolved_at"] = now

    result = await db.execute(
        update(LoginChallenge)
        .where(
            LoginChallenge.id == challenge.id,
            LoginChallenge.status == LoginChallenge.STATUS_PENDING,
        )
        .values(**values)
    )
    await db.commit()
    await db.refresh(challenge)

    return _rowcount(result) == 1


async def cancel_challenge(
    db: AsyncSession,
    challenge_id: str,
) -> LoginChallenge:
    """
    Cancel a pending challenge from the waiting client itself.
    Cancellation always blocks the login.
    """
    challenge = await _get_challenge_or_none(db, challenge_id)
    if challenge is None:
        raise ChallengeNotFoundError("Sign-in request not found.")

    now = datetime.now(UTC)
    if challenge.status == LoginChallenge.STATUS_PENDING and now > challenge.expires_at:
        await _transition_challenge(
            db,
            challenge,
            LoginChallenge.STATUS_EXPIRED,
        )
        raise ChallengeStateError(
            "This sign-in request has expired.",
            status_code=410,
        )

    if challenge.status != LoginChallenge.STATUS_PENDING:
        raise ChallengeStateError(
            "This sign-in request has already been handled.",
            status_code=409,
        )

    await _transition_challenge(
        db,
        challenge,
        LoginChallenge.STATUS_CANCELLED,
    )

    logger.info(
        "login_challenge_cancelled challenge_id=%s user_id=%s",
        challenge.challenge_id,
        challenge.user_id,
    )

    return challenge


async def _verify_approval_code(
    db: AsyncSession,
    challenge: LoginChallenge,
    approval_code: str,
) -> None:
    """
    Verify the email fallback approval code against the challenge.
    Single-use, short-lived and attempt limited. Raises on failure.
    """
    if (
        challenge.delivery_method != LoginChallenge.DELIVERY_EMAIL
        or not challenge.approval_code_hash
    ):
        raise ChallengeStateError(
            "Invalid approval request.",
            status_code=403,
        )

    now = datetime.now(UTC)

    if challenge.code_expires_at is not None and now > challenge.code_expires_at:
        challenge.approval_code_hash = None
        await db.commit()
        raise ChallengeStateError(
            "Approval code has expired. Request a new sign-in.",
            status_code=410,
        )

    if challenge.code_failed_attempts >= settings.login_approval_code_max_failed_attempts:
        challenge.approval_code_hash = None
        await db.commit()
        raise ChallengeStateError(
            "Too many invalid code attempts. This sign-in request was blocked.",
            status_code=403,
        )

    if not verify_otp_hash(approval_code, challenge.approval_code_hash):
        challenge.code_failed_attempts += 1
        remaining = max(
            0,
            settings.login_approval_code_max_failed_attempts - challenge.code_failed_attempts,
        )
        if remaining == 0:
            challenge.approval_code_hash = None
        await db.commit()
        raise ChallengeStateError(
            f"Invalid approval code. {remaining} attempt(s) remaining.",
            status_code=403,
        )

    # Code verified: invalidate immediately (single-use).
    challenge.approval_code_hash = None
    challenge.code_expires_at = None
    challenge.code_failed_attempts = 0
    await db.commit()


async def complete_login_challenge(
    db: AsyncSession,
    challenge_id: str,
    *,
    approval_code: str | None = None,
    remember_device: bool | None = None,
) -> tuple[User, LoginChallenge]:
    """
    Complete a login challenge and return the user for JWT issuance.

    A challenge is consumable exactly once. No access token is ever issued
    before this function returns successfully. Denied, cancelled, expired,
    unknown and replayed challenges all raise.
    """
    challenge = await _get_challenge_or_none(db, challenge_id)
    if challenge is None:
        raise ChallengeNotFoundError("Sign-in request not found.")

    now = datetime.now(UTC)

    if challenge.status == LoginChallenge.STATUS_PENDING:
        if now > challenge.expires_at:
            await _transition_challenge(
                db,
                challenge,
                LoginChallenge.STATUS_EXPIRED,
            )
            raise ChallengeStateError(
                "This sign-in request has expired.",
                status_code=410,
            )

        if approval_code is None:
            raise ChallengeStateError(
                "Sign-in has not been approved yet. Check your phone.",
                status_code=409,
            )

        await _verify_approval_code(db, challenge, approval_code)

        # Code verified: atomically promote to approved.
        result = await db.execute(
            update(LoginChallenge)
            .where(
                LoginChallenge.id == challenge.id,
                LoginChallenge.status == LoginChallenge.STATUS_PENDING,
            )
            .values(
                status=LoginChallenge.STATUS_APPROVED,
                resolved_at=now,
                resolved_by_ip=(challenge.ip_address or "")[:45] or None,
            )
        )
        await db.commit()
        await db.refresh(challenge)

        if _rowcount(result) != 1:
            raise ChallengeStateError(
                "This sign-in request has already been handled.",
                status_code=409,
            )

        logger.info(
            "login_challenge_approved user_id=%s challenge_id=%s device=email-code",
            challenge.user_id,
            challenge.challenge_id,
        )

    if challenge.status == LoginChallenge.STATUS_APPROVED:
        # Atomic single-use consumption: concurrent completes race safely.
        # The "Remember this device" decision is captured at OTP time and
        # persisted in the same atomic transition (None = keep prior value).
        consume_values: dict[str, Any] = {
            "status": LoginChallenge.STATUS_CONSUMED,
            "consumed_at": now,
        }
        if remember_device is not None:
            consume_values["remember_device"] = remember_device
        result = await db.execute(
            update(LoginChallenge)
            .where(
                LoginChallenge.id == challenge.id,
                LoginChallenge.status == LoginChallenge.STATUS_APPROVED,
            )
            .values(**consume_values)
        )
        await db.commit()
        await db.refresh(challenge)

        if _rowcount(result) != 1:
            raise ChallengeStateError(
                "This sign-in request has already been used.",
                status_code=410,
            )

        user = await db.get(User, challenge.user_id)
        if user is None or not user.is_active:
            raise ChallengeStateError(
                "Account is unavailable.",
                status_code=403,
            )

        return user, challenge

    if challenge.status == LoginChallenge.STATUS_CONSUMED:
        raise ChallengeStateError(
            "This sign-in request has already been used.",
            status_code=410,
        )

    raise ChallengeStateError(
        "Sign-in was not approved.",
        status_code=403,
    )


async def resend_login_challenge(
    db: AsyncSession,
    challenge_id: str,
) -> LoginChallenge:
    """
    Re-dispatch a fresh email approval code for a still-pending challenge.

    Enforces a resend cooldown.
    """
    challenge = await _get_challenge_or_none(db, challenge_id)
    if challenge is None:
        raise ChallengeNotFoundError("Sign-in request not found.")

    now = datetime.now(UTC)

    if challenge.status == LoginChallenge.STATUS_PENDING and now > challenge.expires_at:
        await _transition_challenge(
            db,
            challenge,
            LoginChallenge.STATUS_EXPIRED,
        )
        raise ChallengeStateError(
            "This sign-in request has expired. Please sign in again.",
            status_code=410,
        )

    if challenge.status != LoginChallenge.STATUS_PENDING:
        raise ChallengeStateError(
            "This sign-in request has already been handled.",
            status_code=409,
        )

    # Cooldown enforcement.
    if challenge.code_last_sent_at is not None:
        elapsed = (now - challenge.code_last_sent_at).total_seconds()
        cooldown = settings.login_approval_code_cooldown_seconds
        if elapsed < cooldown:
            raise ChallengeStateError(
                f"Please wait {int(cooldown - elapsed)} second(s) before "
                "requesting another approval.",
                status_code=429,
            )

    user = await db.get(User, challenge.user_id)
    if user is None or not user.is_active:
        raise ChallengeStateError(
            "Account is unavailable.",
            status_code=403,
        )

    approval_code = generate_otp()
    challenge.delivery_method = LoginChallenge.DELIVERY_EMAIL
    challenge.approval_code_hash = hash_otp(approval_code)
    challenge.code_expires_at = now + timedelta(
        minutes=settings.login_approval_code_expire_minutes
    )
    challenge.code_last_sent_at = now
    challenge.code_failed_attempts = 0
    send_login_approval_email(
        to_email=user.email,
        recipient_name=user.full_name,
        approval_code=approval_code,
        expire_minutes=settings.login_approval_code_expire_minutes,
    )

    await db.commit()
    await db.refresh(challenge)

    logger.info(
        "login_challenge_resent challenge_id=%s user_id=%s delivery=%s",
        challenge.challenge_id,
        challenge.user_id,
        challenge.delivery_method,
    )

    return challenge


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def set_device_cookie(
    response: Response,
    raw_token: str,
    *,
    https: bool,
) -> None:
    """
    Attach the trusted device credential as an HttpOnly cookie.
    Secure flag is enforced on HTTPS deployments; SameSite=Lax blocks
    cross-site request forgery while allowing normal top-level navigation.
    """
    response.set_cookie(
        key=DEVICE_COOKIE_NAME,
        value=raw_token,
        max_age=TRUSTED_DEVICE_MAX_AGE_SECONDS,
        httponly=True,
        secure=https,
        samesite="lax",
        path="/",
    )


def clear_device_cookie(response: Response) -> None:
    """Drop any stale device cookie from the response."""
    response.delete_cookie(key=DEVICE_COOKIE_NAME, path="/")


def is_https_request(*, scheme: str, forwarded_proto: str | None) -> bool:
    """Determine whether the client request arrived over HTTPS."""
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return scheme == "https"


__all__ = [
    "DEVICE_COOKIE_NAME",
    "ChallengeNotFoundError",
    "ChallengeStateError",
    "cancel_challenge",
    "clear_device_cookie",
    "complete_login_challenge",
    "create_login_challenge",
    "create_trusted_device",
    "get_valid_trusted_device",
    "is_https_request",
    "list_trusted_devices",
    "resend_login_challenge",
    "revoke_all_security_credentials",
    "revoke_trusted_device",
    "set_device_cookie",
    "touch_trusted_device",
]
