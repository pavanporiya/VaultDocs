"""
Trusted device and Web Push subscription management endpoints.

Lets a signed-in user review and revoke trusted devices and notification
subscriptions from security settings. All mutating routes require a Bearer
token (CSRF-safe: cross-site requests cannot set the header) and operate
strictly on the current user's own resources (no IDOR).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  (needed at runtime by FastAPI path params)

from fastapi import APIRouter, Depends, HTTPException, Request, status

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.core.rate_limit import RateLimitError, rate_limiter
from vaultdocs.core.settings import settings
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User  # noqa: TC001  (needed at runtime by FastAPI)
from vaultdocs.schemas.auth import (
    PushSubscriptionListResponse,
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    TrustedDeviceListResponse,
    TrustedDeviceResponse,
    VapidKeyResponse,
)
from vaultdocs.services.device_approval import (
    DEVICE_COOKIE_NAME,
    ChallengeNotFoundError,
    SubscriptionAlreadyExistsError,
    get_valid_trusted_device,
    list_push_subscriptions,
    list_trusted_devices,
    register_push_subscription,
    revoke_push_subscription,
    revoke_trusted_device,
)
from vaultdocs.services.push import is_push_enabled

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/devices",
    tags=["Trusted Devices & Push"],
)


def _enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Apply an endpoint rate limit, mapping violations to HTTP 429."""
    try:
        rate_limiter.check(key, limit, window_seconds)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


@router.get("", response_model=TrustedDeviceListResponse)
async def list_my_trusted_devices(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrustedDeviceListResponse:
    """
    List the current user's trusted devices, marking the active one.
    """
    devices = await list_trusted_devices(db, current_user.id)

    current_device = await get_valid_trusted_device(
        db,
        current_user.id,
        request.cookies.get(DEVICE_COOKIE_NAME),
    )

    responses = [
        TrustedDeviceResponse.model_validate(device).model_copy(
            update={"is_current": current_device is not None and device.id == current_device.id}
        )
        for device in devices
    ]

    return TrustedDeviceListResponse(devices=responses)


@router.delete("/{device_id}", response_model=TrustedDeviceResponse)
async def revoke_my_trusted_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrustedDeviceResponse:
    """
    Revoke one trusted device. The next sign-in from that device will require
    approval again.
    """
    try:
        device = await revoke_trusted_device(db, current_user.id, device_id)
    except ChallengeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found.",
        ) from exc

    return TrustedDeviceResponse.model_validate(device)


@router.post(
    "/push-subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_my_push_subscription(
    request_data: PushSubscriptionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionResponse:
    """
    Register (or rotate) this browser's Web Push subscription so the account
    can receive "Are you trying to sign in to VaultDocs?" approvals.
    """
    _enforce_rate_limit(
        f"push-register:{current_user.id}",
        settings.rate_limit_approve_attempts,
        settings.rate_limit_poll_window_seconds,
    )

    try:
        subscription = await register_push_subscription(
            db,
            current_user.id,
            endpoint=request_data.endpoint,
            p256dh=request_data.keys.p256dh,
            auth=request_data.keys.auth,
            device_name=request_data.device_name,
            user_agent=request.headers.get("user-agent"),
        )
    except SubscriptionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PushSubscriptionResponse.model_validate(subscription)


@router.get("/push-subscriptions", response_model=PushSubscriptionListResponse)
async def list_my_push_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionListResponse:
    """
    List the current user's active push subscriptions (no encryption keys).
    """
    subscriptions = await list_push_subscriptions(db, current_user.id)
    return PushSubscriptionListResponse(
        subscriptions=[
            PushSubscriptionResponse.model_validate(subscription)
            for subscription in subscriptions
        ]
    )


@router.delete(
    "/push-subscriptions/{subscription_id}",
    response_model=PushSubscriptionResponse,
)
async def revoke_my_push_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionResponse:
    """
    Remove one push subscription so sign-in approvals stop being delivered
    to that device.
    """
    try:
        subscription = await revoke_push_subscription(
            db,
            current_user.id,
            subscription_id,
        )
    except ChallengeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification subscription not found.",
        ) from exc

    return PushSubscriptionResponse.model_validate(subscription)


@router.get("/vapid-public-key", response_model=VapidKeyResponse)
async def get_vapid_public_key() -> VapidKeyResponse:
    """
    Return the VAPID public key used by the PWA to subscribe to push.
    The public key is not a secret.
    """
    if not is_push_enabled():
        return VapidKeyResponse(enabled=False, public_key=None)

    return VapidKeyResponse(
        enabled=True,
        public_key=settings.vapid_public_key,
    )
