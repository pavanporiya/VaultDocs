"""
Device approval service: trusted devices, login challenges, push subscriptions.

Security model
--------------
* A login from an untrusted device creates a short-lived, single-use,
  user-bound challenge. No JWT is issued before the challenge is approved
  and consumed.
* Approval requires an authenticated trusted-device session (JWT + valid
  trusted-device cookie) belonging to the *same* user. The untrusted session
  can never approve itself.
* When no trusted phone (push subscription) is registered, approval falls
  back to the existing secure email OTP channel; approval is never bypassed.
* Only hashes of device credentials, challenge ids and approval codes are
  stored. Push payloads contain no passwords, JWTs or reusable secrets.
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
from vaultdocs.models.push_subscription import PushSubscription
from vaultdocs.models.trusted_device import TrustedDevice
from vaultdocs.models.user import User
from vaultdocs.services.email import (
    send_login_approval_email,
)
from vaultdocs.services.push import (
    PushConfigError,
    PushDeliveryError,
    SubscriptionGoneError,
    is_push_enabled,
    send_push,
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


class SubscriptionAlreadyExistsError(Exception):
    """Raised when a push endpoint is registered to another account."""


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
    Revoke every trusted device and push subscription for a user.

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
    subscription_result = await db.execute(
        update(PushSubscription)
        .where(
            PushSubscription.user_id == user_id,
            PushSubscription.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.commit()

    revoked = _rowcount(device_result) + _rowcount(subscription_result)
    logger.info(
        "security_credentials_revoked user_id=%s revoked_count=%s",
        user_id,
        revoked,
    )
    return revoked


# ---------------------------------------------------------------------------
# Push subscriptions
# ---------------------------------------------------------------------------


async def get_active_push_subscriptions(
    db: AsyncSession,
    user_id: UUID,
) -> list[PushSubscription]:
    """Return non-revoked, non-expired push subscriptions for a user."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.revoked_at.is_(None),
            PushSubscription.expires_at > now,
        )
    )
    return list(result.scalars().all())


async def register_push_subscription(
    db: AsyncSession,
    user_id: UUID,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    device_name: str | None,
    user_agent: str | None,
) -> PushSubscription:
    """
    Register (or rotate) a Web Push subscription for the current user.
    """
    now = datetime.now(UTC)
    clean_endpoint = endpoint.strip()

    existing = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == clean_endpoint
        )
    )

    if existing is not None and existing.user_id != user_id:
        raise SubscriptionAlreadyExistsError(
            "This notification endpoint is registered to another account."
        )

    if existing is not None:
        # Rotation: refresh keys and clear any previous revocation state.
        existing.p256dh = p256dh
        existing.auth = auth
        existing.device_name = (device_name or "").strip()[:100] or None
        existing.user_agent = (user_agent or "").strip()[:255] or None
        existing.failure_count = 0
        existing.revoked_at = None
        existing.expires_at = now + timedelta(
            days=settings.push_subscription_expire_days
        )
        await db.commit()
        await db.refresh(existing)
        return existing

    subscription = PushSubscription(
        user_id=user_id,
        endpoint=clean_endpoint[:1024],
        p256dh=p256dh,
        auth=auth,
        device_name=(device_name or "").strip()[:100] or None,
        user_agent=(user_agent or "").strip()[:255] or None,
        expires_at=now + timedelta(days=settings.push_subscription_expire_days),
    )

    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    logger.info(
        "push_subscription_registered user_id=%s subscription_id=%s",
        user_id,
        subscription.id,
    )

    return subscription


async def list_push_subscriptions(
    db: AsyncSession,
    user_id: UUID,
) -> list[PushSubscription]:
    """List active push subscriptions for a user (newest first)."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(PushSubscription)
        .where(
            PushSubscription.user_id == user_id,
            PushSubscription.revoked_at.is_(None),
            PushSubscription.expires_at > now,
        )
        .order_by(PushSubscription.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_push_subscription(
    db: AsyncSession,
    user_id: UUID,
    subscription_id: UUID,
) -> PushSubscription:
    """
    Revoke a single push subscription. Raises ChallengeNotFoundError when the
    subscription does not exist or belongs to another user.
    """
    subscription = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.id == subscription_id,
            PushSubscription.user_id == user_id,
        )
    )
    if subscription is None:
        raise ChallengeNotFoundError("Notification subscription not found.")

    if subscription.revoked_at is None:
        subscription.revoked_at = datetime.now(UTC)
        await db.commit()
        logger.info(
            "push_subscription_revoked user_id=%s subscription_id=%s",
            user_id,
            subscription_id,
        )

    return subscription


async def _dispatch_push_to_devices(
    db: AsyncSession,
    user_id: UUID,
    payload: dict[str, Any],
) -> bool:
    """
    Send `payload` to every active subscription of `user_id`.

    Returns True when at least one delivery succeeded. Gone subscriptions
    (404/410) are removed; transient failures are counted so repeated
    failures can indicate an unhealthy device. Never raises.
    """
    subscriptions = await get_active_push_subscriptions(db, user_id)
    if not subscriptions:
        return False

    delivered = 0
    now = datetime.now(UTC)

    for subscription in subscriptions:
        try:
            send_push(
                endpoint=subscription.endpoint,
                p256dh=subscription.p256dh,
                auth=subscription.auth,
                payload=payload,
            )
        except SubscriptionGoneError:
            subscription.revoked_at = now
            continue
        except (PushDeliveryError, PushConfigError):
            subscription.failure_count += 1
            continue

        subscription.last_success_at = now
        subscription.failure_count = 0
        delivered += 1

    await db.commit()

    return delivered > 0


# ---------------------------------------------------------------------------
# Login challenges
# ---------------------------------------------------------------------------


def _build_push_payload(challenge_id: str, user_full_name: str) -> dict[str, Any]:
    """
    Build the push payload for a login approval prompt.

    Contains no password, JWT, device credential or reusable approval
    secret. The challenge id is opaque, single-use, short-lived and only
    lets the *trusted* phone act on the prompt.
    """
    return {
        "title": "VaultDocs sign-in approval",
        "body": "Are you trying to sign in to VaultDocs?",
        "tag": f"vaultdocs-login-{challenge_id[:12]}",
        "url": f"/approve-login?challenge={challenge_id}",
        "challenge_id": challenge_id,
        "requested_by": user_full_name,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def _get_challenge_or_none(
    db: AsyncSession,
    challenge_id: str,
) -> LoginChallenge | None:
    result = await db.execute(
        select(LoginChallenge).where(
            LoginChallenge.challenge_id == challenge_id
        )
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
    untrusted device. Dispatches a Web Push prompt when a trusted phone is
    registered, otherwise falls back to the secure email approval code.
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
        expires_at=now + timedelta(
            seconds=settings.login_challenge_expire_seconds
        ),
    )

    pushed = False
    if is_push_enabled():
        pushed = await _dispatch_push_to_devices(
            db,
            user.id,
            _build_push_payload(challenge.challenge_id, user.full_name),
        )

    if pushed:
        challenge.delivery_method = LoginChallenge.DELIVERY_PUSH
    else:
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
        "login_challenge_created user_id=%s challenge_id=%s delivery=%s "
        "remember_device=%s ip=%s",
        user.id,
        challenge.challenge_id,
        challenge.delivery_method,
        remember_device,
        ip_address,
    )

    return challenge


async def get_challenge_status(
    db: AsyncSession,
    challenge_id: str,
) -> dict[str, Any]:
    """
    Return the sanitized status of a challenge, lazily expiring it.
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

    remaining = (challenge.expires_at - now).total_seconds()
    return {
        "status": challenge.status,
        "expires_in_seconds": max(0, int(remaining)),
    }


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


async def resolve_challenge(
    db: AsyncSession,
    challenge_id: str,
    *,
    approver: User,
    approver_device: TrustedDevice,
    approve: bool,
    ip_address: str | None,
) -> LoginChallenge:
    """
    Approve or deny a pending challenge from an authenticated trusted device.

    Guards: same-user only (no IDOR), trusted device required, the
    initiating session can never approve itself, pending + unexpired only,
    and the transition is atomic so a challenge resolves exactly once.
    """
    challenge = await _get_challenge_or_none(db, challenge_id)
    if challenge is None or challenge.user_id != approver.id:
        # Identical error for unknown and foreign challenges: no IDOR probe.
        raise ChallengeNotFoundError("Sign-in request not found.")

    if (
        challenge.device_id_hash is not None
        and challenge.device_id_hash == approver_device.device_token_hash
    ):
        raise ChallengeStateError(
            "This device cannot approve its own sign-in request.",
            status_code=403,
        )

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

    target = (
        LoginChallenge.STATUS_APPROVED if approve else LoginChallenge.STATUS_DENIED
    )

    result = await db.execute(
        update(LoginChallenge)
        .where(
            LoginChallenge.id == challenge.id,
            LoginChallenge.status == LoginChallenge.STATUS_PENDING,
        )
        .values(
            status=target,
            resolved_at=now,
            resolved_by_device_id=approver_device.id,
            resolved_by_ip=(ip_address or "").strip()[:45] or None,
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
        "login_challenge_%s user_id=%s challenge_id=%s device_id=%s ip=%s",
        target,
        approver.id,
        challenge.challenge_id,
        approver_device.id,
        ip_address,
    )

    return challenge


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
            settings.login_approval_code_max_failed_attempts
            - challenge.code_failed_attempts,
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
        result = await db.execute(
            update(LoginChallenge)
            .where(
                LoginChallenge.id == challenge.id,
                LoginChallenge.status == LoginChallenge.STATUS_APPROVED,
            )
            .values(
                status=LoginChallenge.STATUS_CONSUMED,
                consumed_at=now,
            )
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
    Re-dispatch the approval prompt for a still-pending challenge.

    Enforces a resend cooldown. Falls back to the email approval code when
    push delivery is unavailable.
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

    # Cooldown enforcement (shared between push and email resends).
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

    pushed = False
    if challenge.delivery_method == LoginChallenge.DELIVERY_PUSH:
        pushed = await _dispatch_push_to_devices(
            db,
            user.id,
            _build_push_payload(challenge.challenge_id, user.full_name),
        )

    if not pushed:
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
    "SubscriptionAlreadyExistsError",
    "cancel_challenge",
    "clear_device_cookie",
    "complete_login_challenge",
    "create_login_challenge",
    "create_trusted_device",
    "get_challenge_status",
    "get_valid_trusted_device",
    "is_https_request",
    "list_push_subscriptions",
    "list_trusted_devices",
    "register_push_subscription",
    "resend_login_challenge",
    "resolve_challenge",
    "revoke_all_security_credentials",
    "revoke_push_subscription",
    "revoke_trusted_device",
    "set_device_cookie",
    "touch_trusted_device",
]
