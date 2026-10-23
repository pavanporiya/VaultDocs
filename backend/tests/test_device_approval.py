"""
Tests for the device-approval sign-in flow: trusted devices, login
challenges, Web Push approvals, email approval-code fallback, revocation,
rate limiting and audit-relevant security properties.

All tests run against the isolated VaultDocs_test database only
(hard-guarded in conftest) and never touch the network: SMTP and Web Push
are served by the in-memory mock outboxes.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest
from sqlalchemy import select

from vaultdocs.core.security import create_access_token, sha256_hex
from vaultdocs.core.settings import settings
from vaultdocs.main import app
from vaultdocs.models.login_challenge import LoginChallenge
from vaultdocs.models.push_subscription import PushSubscription
from vaultdocs.models.trusted_device import TrustedDevice
from vaultdocs.services.device_approval import (
    DEVICE_COOKIE_NAME,
    ChallengeStateError,
    create_trusted_device,
    resolve_challenge,
)
from vaultdocs.services.email import get_test_outbox
from vaultdocs.services.push import get_push_outbox

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from vaultdocs.models.user import User

PASSWORD = "Password123!"  # noqa: S105

# Valid-looking VAPID material (65-byte uncompressed point / 32-byte scalar).
_VALID_VAPID_PUBLIC = base64.urlsafe_b64encode(
    b"\x04" + bytes(range(64))
).decode().rstrip("=")
_VALID_VAPID_PRIVATE = base64.urlsafe_b64encode(
    bytes(range(100, 132))
).decode().rstrip("=")


@pytest.fixture
def push_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure valid-looking VAPID keys so the push channel activates."""
    monkeypatch.setattr(settings, "vapid_public_key", _VALID_VAPID_PUBLIC)
    monkeypatch.setattr(settings, "vapid_private_key", _VALID_VAPID_PRIVATE)


def _login_payload(email: str, remember: bool = False) -> dict[str, Any]:
    return {
        "email": email,
        "password": PASSWORD,
        "remember_device": remember,
    }


def _latest_login_approval_code() -> str:
    entries = [
        entry for entry in get_test_outbox() if entry.get("type") == "login_approval"
    ]
    assert entries, "Expected a login approval email in the mock outbox."
    return str(entries[-1]["otp_code"])


async def _challenge_from_login(
    client: AsyncClient,
    email: str,
    remember: bool = False,
) -> dict[str, Any]:
    response = await client.post(
        "/v1/auth/login",
        json=_login_payload(email, remember=remember),
    )
    assert response.status_code == 202, response.text
    body = cast("dict[str, Any]", response.json())
    assert body["approval_required"] is True
    assert "access_token" not in body
    return body


async def _trusted_approver_headers(
    db_session: AsyncSession,
    user: User,
) -> tuple[dict[str, str], dict[str, str]]:
    """Create a trusted device for `user`; return (auth headers, cookies)."""
    _device, raw_token = await create_trusted_device(
        db_session,
        user.id,
        device_name="Trusted Phone",
        user_agent="pytest-phone",
        ip_address="10.0.0.2",
    )
    headers = {"Authorization": f"Bearer {create_access_token(subject=user.email)}"}
    cookies = {DEVICE_COOKIE_NAME: raw_token}
    return headers, cookies


# ===========================================================================
# Login branches: trusted vs untrusted device
# ===========================================================================


class TestLoginBranches:
    async def test_invalid_password_gets_generic_error(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        response = await client.post(
            "/v1/auth/login",
            json={**_login_payload(user_a.email), "password": "WrongPass123!"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."

    async def test_unknown_email_gets_same_generic_error(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/v1/auth/login",
            json=_login_payload("nobody@example.com"),
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."

    async def test_new_device_requires_approval_email_fallback(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        assert body["delivery"] == "email"
        assert "Check your phone" in body["message"] or "emailed" in body["message"]
        assert body["expires_in_seconds"] > 0

        # No JWT was issued before approval.
        me = await client.get("/v1/auth/me")
        assert me.status_code == 401

        # The approval code arrived through the mocked email channel.
        assert _latest_login_approval_code()

    async def test_trusted_device_login_skips_approval(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        _device, raw_token = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="Laptop",
            user_agent="pytest",
            ip_address="10.0.0.1",
        )

        response = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["access_token"]
        assert body["device_remembered"] is True

        me = await client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me.status_code == 200

    async def test_expired_trust_requires_approval(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        device, raw_token = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="Old Laptop",
            user_agent="pytest",
            ip_address="10.0.0.1",
        )
        device.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db_session.commit()

        response = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )
        assert response.status_code == 202
        assert response.json()["approval_required"] is True

    async def test_revoked_trust_requires_approval(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        device, raw_token = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="Revoked Phone",
            user_agent="pytest",
            ip_address="10.0.0.1",
        )
        device.revoked_at = datetime.now(UTC)
        await db_session.commit()

        response = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )
        assert response.status_code == 202

    async def test_stale_device_cookie_cleared_on_untrusted_login(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        response = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
            cookies={DEVICE_COOKIE_NAME: "not-a-real-device-secret"},
        )
        assert response.status_code == 202
        assert any(
            DEVICE_COOKIE_NAME in header
            for header in response.headers.get_list("set-cookie")
        )

    async def test_other_users_valid_trusted_cookie_cannot_bypass_approval(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        user_b: User,
    ) -> None:
        """Regression: the OTP/approval bypass is only granted for a
        server-verified trusted-device record bound to the authenticating
        user. A valid, unexpired cookie belonging to a DIFFERENT user must
        never skip the approval challenge."""
        _device, raw_token_b = await create_trusted_device(
            db_session,
            user_b.id,
            device_name="B's Phone",
            user_agent="pytest",
            ip_address="10.0.0.4",
        )

        response = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
            cookies={DEVICE_COOKIE_NAME: raw_token_b},
        )

        assert response.status_code == 202, response.text
        body = cast("dict[str, Any]", response.json())
        assert body["approval_required"] is True
        assert "access_token" not in body

        # user A's own (separate) trusted record is untouched and still
        # required to come from her own devices.
        user_a_devices = list(
            (
                await db_session.execute(
                    select(TrustedDevice).where(TrustedDevice.user_id == user_a.id)
                )
            ).scalars()
        )
        assert user_a_devices == []


# ===========================================================================
# Approval flows: phone approve/deny, email code, cancel
# ===========================================================================


class TestApprovalFlows:
    async def test_trusted_phone_approve_then_complete(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        user_b: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        headers, cookies = await _trusted_approver_headers(db_session, user_b)
        # user_b approving user_a's challenge must not work (different user).
        foreign = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )
        assert foreign.status_code == 404

        # The real owner approves from their own trusted device.
        headers, cookies = await _trusted_approver_headers(db_session, user_a)
        approve = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["status"] == "approved"

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["access_token"]

    async def test_deny_blocks_login(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        headers, cookies = await _trusted_approver_headers(db_session, user_a)
        deny = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/deny",
            headers=headers,
            cookies=cookies,
        )
        assert deny.status_code == 200
        assert deny.json()["status"] == "denied"

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        assert complete.status_code == 403

    async def test_cancel_blocks_login(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        cancel = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/cancel",
        )
        assert cancel.status_code == 200

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        assert complete.status_code == 403

    async def test_expired_challenge_blocks_login(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        challenge = await db_session.scalar(
            select(LoginChallenge).where(
                LoginChallenge.challenge_id == challenge_id
            )
        )
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.commit()

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        assert complete.status_code == 410

    async def test_pending_challenge_complete_requires_approval(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        complete = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/complete",
            json={},
        )
        assert complete.status_code == 409

    async def test_poll_reports_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        poll = await client.get(f"/v1/auth/login/challenges/{challenge_id}")
        assert poll.status_code == 200
        assert poll.json()["status"] == "pending"

        headers, cookies = await _trusted_approver_headers(db_session, user_a)
        await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )

        poll = await client.get(f"/v1/auth/login/challenges/{challenge_id}")
        assert poll.json()["status"] == "approved"

    async def test_unknown_challenge_is_generic_404(
        self,
        client: AsyncClient,
    ) -> None:
        poll = await client.get("/v1/auth/login/challenges/does-not-exist")
        assert poll.status_code == 404


# ===========================================================================
# Email approval code fallback
# ===========================================================================


class TestEmailApprovalCode:
    async def test_wrong_code_rejected_then_right_code_works(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        wrong = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": "000000"},
        )
        assert wrong.status_code == 403

        code = _latest_login_approval_code()
        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["access_token"]

    async def test_max_failed_attempts_invalidates_code(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        for _ in range(settings.login_approval_code_max_failed_attempts):
            response = await client.post(
                f"/v1/auth/login/challenges/{challenge_id}/complete",
                json={"approval_code": "000000"},
            )
            assert response.status_code == 403

        # Even the correct code is now rejected — sign-in stays blocked.
        code = _latest_login_approval_code()
        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
        )
        assert complete.status_code in (403, 410)

    async def test_code_is_single_use(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        code = _latest_login_approval_code()

        first = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
        )
        assert first.status_code == 200

        replay = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
        )
        assert replay.status_code == 410

    async def test_resend_cooldown_and_rotation(
        self,
        client: AsyncClient,
        user_a: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        old_code = _latest_login_approval_code()

        too_fast = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/resend",
        )
        assert too_fast.status_code == 429

        # After the cooldown, a fresh code is issued and the old one dies.
        monkeypatch.setattr(settings, "login_approval_code_cooldown_seconds", 0)

        resent = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/resend",
        )
        assert resent.status_code == 200, resent.text
        assert resent.json()["delivery"] == "email"

        new_code = _latest_login_approval_code()
        assert new_code != old_code

        stale = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": old_code},
        )
        assert stale.status_code == 403

        fresh = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": new_code},
        )
        assert fresh.status_code == 200


# ===========================================================================
# Remember this device (30 days)
# ===========================================================================


class TestRememberDevice:
    async def test_unchecked_remember_never_grants_trust(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        headers, cookies = await _trusted_approver_headers(db_session, user_a)
        await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        assert complete.status_code == 200
        assert complete.json()["device_remembered"] is False

        devices = list(
            (
                await db_session.execute(
                    select(TrustedDevice).where(TrustedDevice.user_id == user_a.id)
                )
            ).scalars()
        )
        # Only the approver's device exists; completing created no new trust.
        assert len(devices) == 1

        # Next login from the (untrusted) client still requires approval.
        follow_up = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
        )
        assert follow_up.status_code == 202

    async def test_checked_remember_creates_exactly_30_day_trust(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email, remember=True)
        challenge_id = body["challenge_id"]

        headers, cookies = await _trusted_approver_headers(db_session, user_a)
        await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": None, "device_name": "New Laptop"},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["device_remembered"] is True
        assert any(
            DEVICE_COOKIE_NAME in header
            for header in complete.headers.get_list("set-cookie")
        )

        new_device = await db_session.scalar(
            select(TrustedDevice).where(
                TrustedDevice.user_id == user_a.id,
                TrustedDevice.device_name == "New Laptop",
            )
        )
        assert new_device is not None
        remaining = (new_device.expires_at - datetime.now(UTC)).total_seconds()
        assert 29.9 * 24 * 3600 < remaining <= 30.05 * 24 * 3600

        # The browser now holds the device cookie (httpx keeps it in the
        # jar); the next login is a normal, approval-free login.
        follow_up = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
        )
        assert follow_up.status_code == 200, follow_up.text
        assert follow_up.json()["access_token"]

    async def test_remember_flag_not_honored_without_approval(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        """A remembered login still needs approval first — trust is opt-in
        and never granted automatically."""
        response = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email, remember=True),
        )
        assert response.status_code == 202
        assert "access_token" not in response.json()


# ===========================================================================# Web Push approvals
# ===========================================================================


class TestWebPush:
    async def test_push_delivery_used_when_subscription_exists(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        push_enabled: None,
    ) -> None:
        await client.post(
            "/v1/devices/push-subscriptions",
            json={
                "endpoint": "https://push.example.com/sub-1",
                "keys": {
                    "p256dh": "B" * 87,
                    "auth": "c" * 32,
                },
                "device_name": "Pixel",
            },
            headers={"Authorization": f"Bearer {create_access_token(subject=user_a.email)}"},
        )

        body = await _challenge_from_login(client, user_a.email)
        assert body["delivery"] == "push"

        outbox = get_push_outbox()
        assert outbox, "Expected a push notification in the mock outbox."
        payload = outbox[-1]["payload"]

        # Prompt copy required by the product spec.
        assert payload["title"] == "VaultDocs sign-in approval"
        assert payload["body"] == "Are you trying to sign in to VaultDocs?"
        assert payload["challenge_id"] == body["challenge_id"]

        # Push payloads must never carry credentials or reusable secrets.
        serialized = str(payload).lower()
        assert PASSWORD.lower() not in serialized
        assert "access_token" not in serialized
        assert "password" not in serialized
        assert "'jwt':" not in serialized
        assert '"jwt":' not in serialized

    async def test_push_failure_falls_back_to_email(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        push_enabled: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vaultdocs.services import push as push_service

        await client.post(
            "/v1/devices/push-subscriptions",
            json={
                "endpoint": "https://push.example.com/sub-flaky",
                "keys": {"p256dh": "B" * 87, "auth": "c" * 32},
            },
            headers={"Authorization": f"Bearer {create_access_token(subject=user_a.email)}"},
        )

        monkeypatch.setattr(push_service, "_mock_push_fail", True)

        body = await _challenge_from_login(client, user_a.email)
        assert body["delivery"] == "email"
        assert _latest_login_approval_code()

    async def test_push_delivery_never_authorizes_login_by_itself(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        push_enabled: None,
    ) -> None:
        """Receiving the push (challenge created) grants nothing: the
        waiting session still cannot complete without approval."""
        await client.post(
            "/v1/devices/push-subscriptions",
            json={
                "endpoint": "https://push.example.com/sub-2",
                "keys": {"p256dh": "B" * 87, "auth": "c" * 32},
            },
            headers={"Authorization": f"Bearer {create_access_token(subject=user_a.email)}"},
        )

        body = await _challenge_from_login(client, user_a.email)
        complete = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/complete",
            json={},
        )
        assert complete.status_code == 409

    async def test_vapid_public_key_discovery(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "vapid_public_key", None)
        monkeypatch.setattr(settings, "vapid_private_key", None)

        disabled = await client.get("/v1/devices/vapid-public-key")
        assert disabled.status_code == 200
        assert disabled.json() == {"enabled": False, "public_key": None}

    async def test_vapid_public_key_discovery_enabled(
        self,
        client: AsyncClient,
        push_enabled: None,
    ) -> None:
        enabled = await client.get("/v1/devices/vapid-public-key")
        assert enabled.json()["enabled"] is True
        assert enabled.json()["public_key"] == _VALID_VAPID_PUBLIC


# ===========================================================================
# Security: self-approval, IDOR, replay, concurrent approvals
# ===========================================================================


class TestSecurityGuards:
    async def test_session_cannot_approve_itself(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        """A trusted cookie presented at login can never be the approver of
        its own challenge — approval must come from another trusted device."""
        _device, raw_token = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="Trusted Phone",
            user_agent="pytest",
            ip_address="10.0.0.2",
        )

        # Simulate a stale trust state on this browser: login requires a
        # challenge while the cookie hash is still recorded on it.
        from vaultdocs.services.device_approval import create_login_challenge

        challenge = await create_login_challenge(
            db_session,
            user_a,
            remember_device=False,
            device_id_hash=sha256_hex(raw_token),
            ip_address="10.0.0.9",
            user_agent="pytest",
        )

        device = await db_session.scalar(
            select(TrustedDevice).where(TrustedDevice.user_id == user_a.id)
        )
        assert device is not None

        with pytest.raises(ChallengeStateError) as excinfo:
            await resolve_challenge(
                db_session,
                challenge.challenge_id,
                approver=user_a,
                approver_device=device,
                approve=True,
                ip_address="10.0.0.9",
            )
        assert excinfo.value.status_code == 403

    async def test_approve_without_trusted_device_rejected(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        # Valid JWT but no trusted-device cookie -> cannot approve.
        approve = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/approve",
            headers={
                "Authorization": f"Bearer {create_access_token(subject=user_a.email)}"
            },
        )
        assert approve.status_code == 403

    async def test_approve_requires_authentication(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        approve = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/approve",
        )
        assert approve.status_code in (401, 403)

    async def test_double_approve_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        headers, cookies = await _trusted_approver_headers(db_session, user_a)

        first = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )
        assert first.status_code == 200

        second = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )
        assert second.status_code == 409

    async def test_foreign_challenge_invisible_to_other_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        user_b: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        headers, cookies = await _trusted_approver_headers(db_session, user_b)

        deny = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/deny",
            headers=headers,
            cookies=cookies,
        )
        assert deny.status_code == 404

    async def test_concurrent_complete_only_one_wins(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        headers, cookies = await _trusted_approver_headers(db_session, user_a)
        await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )

        first = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        second = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={},
        )
        assert first.status_code == 200
        assert second.status_code == 410


# ===========================================================================
# Rate limiting
# ===========================================================================


class TestRateLimiting:
    async def test_login_rate_limited_per_identity(
        self,
        client: AsyncClient,
        user_a: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_login_attempts", 3)

        for _ in range(3):
            response = await client.post(
                "/v1/auth/login",
                json=_login_payload(user_a.email),
            )
            assert response.status_code == 202

        limited = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
        )
        assert limited.status_code == 429

    async def test_polling_rate_limited(
        self,
        client: AsyncClient,
        user_a: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_poll_attempts", 2)

        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]

        for _ in range(2):
            poll = await client.get(f"/v1/auth/login/challenges/{challenge_id}")
            assert poll.status_code == 200

        limited = await client.get(f"/v1/auth/login/challenges/{challenge_id}")
        assert limited.status_code == 429
        assert limited.headers.get("retry-after")

    async def test_challenge_creation_rate_limited(
        self,
        client: AsyncClient,
        user_a: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_challenge_attempts", 2)

        for _ in range(2):
            response = await client.post(
                "/v1/auth/login",
                json=_login_payload(user_a.email),
            )
            assert response.status_code == 202

        limited = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
        )
        assert limited.status_code == 429

    async def test_approval_rate_limited_per_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_approve_attempts", 1)

        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        headers, cookies = await _trusted_approver_headers(db_session, user_a)

        first = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/deny",
            headers=headers,
            cookies=cookies,
        )
        assert first.status_code == 200

        limited = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/approve",
            headers=headers,
            cookies=cookies,
        )
        assert limited.status_code == 429


# ===========================================================================
# Security settings: devices + push subscriptions management
# ===========================================================================


class TestSecuritySettings:
    async def test_list_and_revoke_devices(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        device, raw_token = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="Pixel",
            user_agent="pytest",
            ip_address="10.0.0.5",
        )
        headers = {"Authorization": f"Bearer {create_access_token(subject=user_a.email)}"}

        listing = await client.get(
            "/v1/devices",
            headers=headers,
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )
        assert listing.status_code == 200
        devices = listing.json()["devices"]
        assert len(devices) == 1
        assert devices[0]["is_current"] is True
        assert devices[0]["device_name"] == "Pixel"

        revoke = await client.delete(
            f"/v1/devices/{device.id}",
            headers=headers,
        )
        assert revoke.status_code == 200

        login = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )
        assert login.status_code == 202

    async def test_revoke_foreign_device_is_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        user_b: User,
    ) -> None:
        device, _raw = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="A's phone",
            user_agent="pytest",
            ip_address="10.0.0.6",
        )
        headers_b = {
            "Authorization": f"Bearer {create_access_token(subject=user_b.email)}"
        }
        revoke = await client.delete(f"/v1/devices/{device.id}", headers=headers_b)
        assert revoke.status_code == 404

    async def test_push_subscription_lifecycle(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {create_access_token(subject=user_a.email)}"
        }

        register = await client.post(
            "/v1/devices/push-subscriptions",
            json={
                "endpoint": "https://push.example.com/lifecycle",
                "keys": {"p256dh": "B" * 87, "auth": "c" * 32},
                "device_name": "Phone",
            },
            headers=headers,
        )
        assert register.status_code == 201, register.text
        subscription_id = register.json()["id"]
        # Encryption keys are never echoed back.
        assert "keys" not in register.json()

        listing = await client.get(
            "/v1/devices/push-subscriptions",
            headers=headers,
        )
        assert listing.status_code == 200
        assert len(listing.json()["subscriptions"]) == 1

        revoke = await client.delete(
            f"/v1/devices/push-subscriptions/{subscription_id}",
            headers=headers,
        )
        assert revoke.status_code == 200

        listing = await client.get(
            "/v1/devices/push-subscriptions",
            headers=headers,
        )
        assert listing.json()["subscriptions"] == []

    async def test_push_subscription_rotation_updates_keys(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {create_access_token(subject=user_a.email)}"
        }
        body = {
            "endpoint": "https://push.example.com/rotate",
            "keys": {"p256dh": "B" * 87, "auth": "c" * 32},
        }
        first = await client.post(
            "/v1/devices/push-subscriptions",
            json=body,
            headers=headers,
        )
        assert first.status_code == 201

        rotated = await client.post(
            "/v1/devices/push-subscriptions",
            json={**body, "keys": {"p256dh": "C" * 87, "auth": "d" * 32}},
            headers=headers,
        )
        assert rotated.status_code == 201
        assert rotated.json()["id"] == first.json()["id"]

        subscriptions = list(
            (
                await db_session.execute(
                    select(PushSubscription).where(
                        PushSubscription.user_id == user_a.id
                    )
                )
            ).scalars()
        )
        assert len(subscriptions) == 1
        assert subscriptions[0].p256dh == "C" * 87

    async def test_foreign_subscription_is_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
        user_b: User,
    ) -> None:
        headers_a = {
            "Authorization": f"Bearer {create_access_token(subject=user_a.email)}"
        }
        register = await client.post(
            "/v1/devices/push-subscriptions",
            json={
                "endpoint": "https://push.example.com/owned-by-a",
                "keys": {"p256dh": "B" * 87, "auth": "c" * 32},
            },
            headers=headers_a,
        )
        subscription_id = register.json()["id"]

        headers_b = {
            "Authorization": f"Bearer {create_access_token(subject=user_b.email)}"
        }
        revoke = await client.delete(
            f"/v1/devices/push-subscriptions/{subscription_id}",
            headers=headers_b,
        )
        assert revoke.status_code == 404

    async def test_unauthenticated_cannot_manage_devices(
        self,
        client: AsyncClient,
    ) -> None:
        listing = await client.get("/v1/devices")
        assert listing.status_code in (401, 403)


# ===========================================================================
# Security events revoke trust
# ===========================================================================


class TestCredentialEventRevocation:
    async def test_password_reset_revokes_devices_and_subscriptions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        device, raw_token = await create_trusted_device(
            db_session,
            user_a.id,
            device_name="Old Phone",
            user_agent="pytest",
            ip_address="10.0.0.7",
        )
        subscription = PushSubscription(
            user_id=user_a.id,
            endpoint="https://push.example.com/reset-me",
            p256dh="B" * 87,
            auth="c" * 32,
            expires_at=datetime.now(UTC) + timedelta(days=60),
        )
        db_session.add(subscription)
        await db_session.commit()

        # Drive the real password-reset flow end to end.
        forgot = await client.post(
            "/v1/auth/forgot-password",
            json={"email": user_a.email},
        )
        assert forgot.status_code == 200

        reset_entries = [
            entry for entry in get_test_outbox() if entry.get("type") == "password_reset"
        ]
        assert reset_entries
        reset_token = reset_entries[-1]["reset_token"]

        reset = await client.post(
            "/v1/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "BrandNewPass123!",
                "email": user_a.email,
            },
        )
        assert reset.status_code == 200, reset.text

        await db_session.refresh(device)
        assert device.revoked_at is not None

        refreshed_subscription = await db_session.scalar(
            select(PushSubscription).where(PushSubscription.id == subscription.id)
        )
        assert refreshed_subscription is not None
        assert refreshed_subscription.revoked_at is not None

        # The old device cookie no longer trusts this browser.
        login = await client.post(
            "/v1/auth/login",
            json={**_login_payload(user_a.email), "password": "BrandNewPass123!"},
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )
        assert login.status_code == 202


# ===========================================================================
# VAPID configuration validation
# ===========================================================================


class TestVapidValidation:
    def test_partial_configuration_fails_safely(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "vapid_public_key", _VALID_VAPID_PUBLIC)
        monkeypatch.setattr(settings, "vapid_private_key", None)
        with pytest.raises(RuntimeError, match="VAPID"):
            settings.validate_push_configuration()

    def test_malformed_public_key_fails_safely(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "vapid_public_key", "not-base64url-!!!")
        monkeypatch.setattr(settings, "vapid_private_key", _VALID_VAPID_PRIVATE)
        with pytest.raises(RuntimeError, match="VAPID"):
            settings.validate_push_configuration()

    def test_valid_configuration_passes(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "vapid_public_key", _VALID_VAPID_PUBLIC)
        monkeypatch.setattr(settings, "vapid_private_key", _VALID_VAPID_PRIVATE)
        settings.validate_push_configuration()

    def test_empty_configuration_disables_push(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "vapid_public_key", None)
        monkeypatch.setattr(settings, "vapid_private_key", None)
        settings.validate_push_configuration()


def test_app_registered_challenge_routes() -> None:
    """Sanity: all device-approval routes are wired into the API."""
    # Newer FastAPI keeps included routers nested; the OpenAPI schema is the
    # canonical flattened view of every registered path.
    paths = set(app.openapi()["paths"].keys())
    assert "/v1/auth/login/challenges/{challenge_id}" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/approve" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/deny" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/complete" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/resend" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/cancel" in paths
    assert "/v1/devices" in paths
    assert "/v1/devices/push-subscriptions" in paths


# ===========================================================================
# Regression: approval-completed sign-in must yield a real, durable session
# (bug report: "approved" banner shown, but the sign-in screen returned after
# a page reload — i.e. no usable auth credentials were issued/restored).
# ===========================================================================


class TestApprovalLoginSessionRegression:
    async def test_email_code_complete_issues_usable_persistent_session(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        """
        Complete an email-code approval and verify the issued JWT actually
        authenticates (including a second call, mirroring a page reload that
        restores the session from the stored token) and that the trusted
        device cookie is set when the user asked to be remembered.
        """
        body = await _challenge_from_login(client, user_a.email, remember=True)
        code = _latest_login_approval_code()

        complete = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/complete",
            json={"approval_code": code, "device_name": "Regression Laptop"},
        )
        assert complete.status_code == 200, complete.text
        payload = cast("dict[str, Any]", complete.json())
        token = payload["access_token"]
        assert payload["device_remembered"] is True
        # remember_device=on must mint the 30-day trusted-device cookie
        assert DEVICE_COOKIE_NAME in complete.cookies

        headers = {"Authorization": f"Bearer {token}"}
        # Session works immediately after approval...
        me_first = await client.get("/v1/auth/me", headers=headers)
        assert me_first.status_code == 200, me_first.text
        # ...and still works on the next page load (reload restoration).
        me_reload = await client.get("/v1/auth/me", headers=headers)
        assert me_reload.status_code == 200, me_reload.text
        assert me_reload.json()["email"] == user_a.email

    async def test_logout_then_relogin_on_remembered_device_is_immediate(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        """
        Browser logout only drops the stored JWT; the HttpOnly trusted-device
        cookie survives. The next sign-in must therefore be an immediate,
        approval-free session (the "logout -> signin" step of the report).
        """
        body = await _challenge_from_login(client, user_a.email, remember=True)
        code = _latest_login_approval_code()
        complete = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/complete",
            json={"approval_code": code},
        )
        assert complete.status_code == 200, complete.text
        assert DEVICE_COOKIE_NAME in complete.cookies

        # Simulate browser logout: stored token gone, device cookie kept.
        relogin = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email, remember=True),
        )
        assert relogin.status_code == 200, relogin.text
        relogin_payload = cast("dict[str, Any]", relogin.json())
        assert relogin_payload["device_remembered"] is True
        assert "approval_required" not in relogin_payload

        me = await client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {relogin_payload['access_token']}"},
        )
        assert me.status_code == 200, me.text
        assert me.json()["email"] == user_a.email
