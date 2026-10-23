"""
Web Push delivery service for VaultDocs sign-in approval notifications.

Delivers short-lived, non-authorizing approval prompts to registered
trusted phones/PWA installs. Payloads never contain passwords, JWTs,
raw device credentials or reusable approval secrets — at most the opaque,
single-use challenge id needed for the trusted device to act on the prompt.

Push delivery itself never authorizes a login; approval always requires an
authenticated trusted-device session.

Provides isolated in-memory test hooks (same pattern as the mock SMTP
outbox) so automated tests never touch the network.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from vaultdocs.core.settings import settings

logger = logging.getLogger(__name__)


class PushDeliveryError(RuntimeError):
    """Raised when a Web Push message cannot be delivered."""


class PushConfigError(RuntimeError):
    """Raised when Web Push is used while VAPID keys are not configured."""


class SubscriptionGoneError(RuntimeError):
    """Raised when the push service reports the subscription as gone (404/410)."""


# In-memory outbox and control flags for automated test environments.
_test_push_outbox: list[dict[str, Any]] = []
_mock_push_mode: bool = False
_mock_push_fail: bool = False


def set_mock_push(enabled: bool, *, should_fail: bool = False) -> None:
    """
    Enable or disable mock push mode for automated tests.

    When enabled, notifications are placed in the test outbox without any
    network access. If should_fail is True, PushDeliveryError is raised.
    """
    global _mock_push_mode, _mock_push_fail
    _mock_push_mode = enabled
    _mock_push_fail = should_fail


def get_push_outbox() -> list[dict[str, Any]]:
    """Return delivered push messages captured in test mode."""
    return list(_test_push_outbox)


def clear_push_outbox() -> None:
    """Clear captured push messages."""
    _test_push_outbox.clear()


def is_push_enabled() -> bool:
    """Return True when a complete VAPID key pair is configured."""
    return bool(
        (settings.vapid_public_key or "").strip()
        and (settings.vapid_private_key or "").strip()
    )


def send_push(
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: dict[str, Any],
    ttl_seconds: int = 300,
) -> None:
    """
    Deliver an encrypted Web Push message to a single subscription.

    Raises PushConfigError when VAPID keys are missing, SubscriptionGoneError
    when the push service reports the subscription removed (so callers can
    delete it), and PushDeliveryError for any other delivery failure.
    Never logs payload contents or subscription keys.
    """
    if _mock_push_mode:
        if _mock_push_fail:
            raise PushDeliveryError("Mock push delivery failure for testing.")
        _test_push_outbox.append(
            {
                "endpoint": endpoint,
                "payload": dict(payload),
            }
        )
        return

    if not is_push_enabled():
        raise PushConfigError(
            "Web Push is not configured. Set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY."
        )

    # Imported lazily so the app works without the push extras at runtime.
    from pywebpush import WebPushException, webpush

    subscription_info = {
        "endpoint": endpoint,
        "keys": {"p256dh": p256dh, "auth": auth},
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.vapid_claims_email}"},
            ttl=ttl_seconds,
            timeout=10.0,
        )
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in (404, 410):
            raise SubscriptionGoneError(
                "Push subscription is no longer registered."
            ) from None
        logger.error(
            "Web Push delivery failed (status=%s, type=%s)",
            status_code,
            type(exc).__name__,
        )
        raise PushDeliveryError(
            f"Failed to deliver push notification ({type(exc).__name__})."
        ) from None
    except Exception as exc:
        logger.error("Web Push delivery failed: %s", type(exc).__name__)
        raise PushDeliveryError(
            f"Failed to deliver push notification ({type(exc).__name__})."
        ) from None
