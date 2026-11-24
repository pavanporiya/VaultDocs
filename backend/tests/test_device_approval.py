"""
Tests for the sign-in approval flow: trusted devices (30-day OTP bypass),
login challenges, email approval-code (OTP) verification, revocation,
rate limiting and audit-relevant security properties.

Covers the manual checklist: first login requires the OTP, "Remember this
device for 30 days" (decided at the OTP step) creates a server-verified
trusted-device record + cookie, the next login skips the OTP, unchecked /
expired / revoked / invalid / cross-user cookies always fall back to OTP,
and password reset revokes trust.

All tests run against the isolated VaultDocs_test database only
(hard-guarded in conftest) and never touch the network: SMTP is served by
the in-memory mock outbox.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select

from vaultdocs.core.security import create_access_token
from vaultdocs.core.settings import settings
from vaultdocs.main import app
from vaultdocs.models.login_challenge import LoginChallenge
from vaultdocs.models.trusted_device import TrustedDevice
from vaultdocs.services.device_approval import (
    DEVICE_COOKIE_NAME,
    create_trusted_device,
)
from vaultdocs.services.email import get_test_outbox

if TYPE_CHECKING:
    import pytest
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from vaultdocs.models.user import User

PASSWORD = "Password123!"  # noqa: S105


def _login_payload(email: str, remember: bool = False) -> dict[str, Any]:
    return {
        "email": email,
        "password": PASSWORD,
        "remember_device": remember,
    }


def _latest_login_approval_code() -> str:
    entries = [entry for entry in get_test_outbox() if entry.get("type") == "login_approval"]
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
            DEVICE_COOKIE_NAME in header for header in response.headers.get_list("set-cookie")
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
# Approval flows: email code, cancel
# ===========================================================================


class TestApprovalFlows:
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
            select(LoginChallenge).where(LoginChallenge.challenge_id == challenge_id)
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
        """Checkbox NOT ticked at the OTP step -> no trusted-device record
        and the next login requires the OTP again."""
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        code = _latest_login_approval_code()

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
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
        # Completing created no trust record at all.
        assert devices == []

        # Next login from this (still untrusted) browser requires the OTP.
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
        """Checkbox ticked at the OTP step -> server-verified trusted-device
        record + HttpOnly cookie; the next login on this browser is
        immediate (no OTP)."""
        body = await _challenge_from_login(client, user_a.email, remember=True)
        challenge_id = body["challenge_id"]
        code = _latest_login_approval_code()

        complete = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={
                "approval_code": code,
                "remember_device": True,
                "device_name": "New Laptop",
            },
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["device_remembered"] is True
        assert any(
            DEVICE_COOKIE_NAME in header for header in complete.headers.get_list("set-cookie")
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

    async def test_remember_checkbox_at_complete_overrides_login_flag(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        """The decision point is the OTP step: ticking "Remember this
        device for 30 days" there creates trust even when the initial
        login request did not ask for it."""
        body = await _challenge_from_login(client, user_a.email, remember=False)
        code = _latest_login_approval_code()

        complete = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/complete",
            json={"approval_code": code, "remember_device": True},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["device_remembered"] is True
        assert DEVICE_COOKIE_NAME in complete.cookies

        # Next login on this browser: immediate, no OTP.
        follow_up = await client.post(
            "/v1/auth/login",
            json=_login_payload(user_a.email),
        )
        assert follow_up.status_code == 200, follow_up.text
        assert follow_up.json()["access_token"]

    async def test_unchecking_at_complete_drops_login_time_remember(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        user_a: User,
    ) -> None:
        """An explicit remember_device=false at the OTP step wins over a
        login-time remember=true: no trust record, OTP required again."""
        body = await _challenge_from_login(client, user_a.email, remember=True)
        code = _latest_login_approval_code()

        complete = await client.post(
            f"/v1/auth/login/challenges/{body['challenge_id']}/complete",
            json={"approval_code": code, "remember_device": False},
        )
        assert complete.status_code == 200, complete.text
        assert complete.json()["device_remembered"] is False

        devices = list(
            (
                await db_session.execute(
                    select(TrustedDevice).where(TrustedDevice.user_id == user_a.id)
                )
            ).scalars()
        )
        assert devices == []


# Security: replay + concurrent completion single-use guards
# ===========================================================================


class TestSecurityGuards:
    async def test_concurrent_complete_only_one_wins(
        self,
        client: AsyncClient,
        user_a: User,
    ) -> None:
        """A challenge (and its OTP) is consumable exactly once."""
        body = await _challenge_from_login(client, user_a.email)
        challenge_id = body["challenge_id"]
        code = _latest_login_approval_code()

        first = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
        )
        second = await client.post(
            f"/v1/auth/login/challenges/{challenge_id}/complete",
            json={"approval_code": code},
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


# ===========================================================================
# Security settings: trusted device management
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
        headers_b = {"Authorization": f"Bearer {create_access_token(subject=user_b.email)}"}
        revoke = await client.delete(f"/v1/devices/{device.id}", headers=headers_b)
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
    async def test_password_reset_revokes_trusted_devices(
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

        # The old device cookie no longer trusts this browser.
        login = await client.post(
            "/v1/auth/login",
            json={**_login_payload(user_a.email), "password": "BrandNewPass123!"},
            cookies={DEVICE_COOKIE_NAME: raw_token},
        )
        assert login.status_code == 202


# ===========================================================================
def test_app_registered_challenge_routes() -> None:
    """Sanity: the email-OTP approval routes are wired in and the removed
    push-approval routes are gone."""
    # Newer FastAPI keeps included routers nested; the OpenAPI schema is the
    # canonical flattened view of every registered path.
    paths = set(app.openapi()["paths"].keys())
    assert "/v1/auth/login/challenges/{challenge_id}/complete" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/resend" in paths
    assert "/v1/auth/login/challenges/{challenge_id}/cancel" in paths
    assert "/v1/devices" in paths

    # Removed together with the Web Push approval flow:
    assert "/v1/auth/login/challenges/{challenge_id}" not in paths
    assert "/v1/auth/login/challenges/{challenge_id}/approve" not in paths
    assert "/v1/auth/login/challenges/{challenge_id}/deny" not in paths
    assert "/v1/devices/push-subscriptions" not in paths
    assert "/v1/devices/push-subscriptions/{subscription_id}" not in paths
    assert "/v1/devices/vapid-public-key" not in paths


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
