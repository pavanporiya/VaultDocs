"""
Trusted device management endpoints.

Lets a signed-in user review and revoke trusted devices from security
settings. All mutating routes require a Bearer token (CSRF-safe:
cross-site requests cannot set the header) and operate strictly on the
current user's own resources (no IDOR).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  (needed at runtime by FastAPI path params)

from fastapi import APIRouter, Depends, HTTPException, Request, status

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User  # noqa: TC001  (needed at runtime by FastAPI)
from vaultdocs.schemas.auth import (
    TrustedDeviceListResponse,
    TrustedDeviceResponse,
)
from vaultdocs.services.device_approval import (
    DEVICE_COOKIE_NAME,
    ChallengeNotFoundError,
    get_valid_trusted_device,
    list_trusted_devices,
    revoke_trusted_device,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/devices",
    tags=["Trusted Devices"],
)


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
