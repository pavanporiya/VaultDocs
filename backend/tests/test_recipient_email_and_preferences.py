"""
Integration tests for recipient email exposure in ShareResponse
and profile/preferences endpoints.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Task 2: recipient email in ShareResponse
# ---------------------------------------------------------------------------


async def _create_document(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/v1/documents", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def test_share_response_contains_recipient_email(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_b,
) -> None:
    """POST /shares returns shared_with_email populated."""
    doc_id = await _create_document(client, auth_headers_user_a, "Email Doc")

    resp = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["shared_with_user_id"] == str(user_b.id)
    assert data["shared_with_email"] == user_b.email


async def test_share_list_contains_recipient_emails(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_b,
) -> None:
    """GET /shares returns shared_with_email for every share."""
    doc_id = await _create_document(client, auth_headers_user_a, "Email List Doc")

    create = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert create.status_code == 201

    listing = await client.get(
        f"/v1/documents/{doc_id}/shares",
        headers=auth_headers_user_a,
    )
    assert listing.status_code == 200
    shares = listing.json()
    assert len(shares) == 1
    assert shares[0]["shared_with_email"] == user_b.email


# ---------------------------------------------------------------------------
# Task 3: PATCH /v1/auth/me (profile update)
# ---------------------------------------------------------------------------


async def test_patch_me_updates_full_name(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a,
) -> None:
    """Authenticated user can update their own full_name."""
    resp = await client.patch(
        "/v1/auth/me",
        json={"full_name": "Renamed User A"},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Renamed User A"
    assert data["email"] == user_a.email
    assert data["id"] == str(user_a.id)

    # Persisted: /me reflects the change
    me = await client.get("/v1/auth/me", headers=auth_headers_user_a)
    assert me.json()["full_name"] == "Renamed User A"


async def test_patch_me_ignores_other_fields(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a,
) -> None:
    """PATCH /me must not modify email, flags, or password fields."""
    resp = await client.patch(
        "/v1/auth/me",
        json={
            "full_name": "Still User A",
            "email": "hijack@example.com",
            "is_superuser": True,
            "is_active": False,
        },
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200

    me = await client.get("/v1/auth/me", headers=auth_headers_user_a)
    data = me.json()
    assert data["email"] == user_a.email
    assert data["is_superuser"] is False
    assert data["is_active"] is True


async def test_patch_me_rejects_empty_name(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Whitespace-only full_name is rejected with 400."""
    resp = await client.patch(
        "/v1/auth/me",
        json={"full_name": "   "},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 400


async def test_patch_me_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated PATCH /me is rejected."""
    resp = await client.patch("/v1/auth/me", json={"full_name": "Ghost"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Task 3: user preferences GET/PUT
# ---------------------------------------------------------------------------


async def test_preferences_default_empty(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Fresh user has empty preferences."""
    resp = await client.get("/v1/users/me/preferences", headers=auth_headers_user_a)
    assert resp.status_code == 200
    assert resp.json() == {"preferences": {}}


async def test_preferences_roundtrip(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """PUT stores and GET returns the full preferences object."""
    payload = {
        "theme": "dark",
        "density": "compact",
        "notifications": {"email": True, "security": False},
    }

    put = await client.put(
        "/v1/users/me/preferences",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert put.status_code == 200
    assert put.json()["preferences"] == payload

    get = await client.get("/v1/users/me/preferences", headers=auth_headers_user_a)
    assert get.status_code == 200
    assert get.json()["preferences"] == payload


async def test_preferences_replacement_semantics(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """PUT replaces the whole object rather than merging keys."""
    first = await client.put(
        "/v1/users/me/preferences",
        json={"theme": "dark", "density": "compact"},
        headers=auth_headers_user_a,
    )
    assert first.status_code == 200

    second = await client.put(
        "/v1/users/me/preferences",
        json={"theme": "light"},
        headers=auth_headers_user_a,
    )
    assert second.status_code == 200
    assert second.json()["preferences"] == {"theme": "light"}


async def test_preferences_require_auth(client: AsyncClient) -> None:
    """Unauthenticated preferences access is rejected."""
    get_resp = await client.get("/v1/users/me/preferences")
    assert get_resp.status_code == 401

    put_resp = await client.put("/v1/users/me/preferences", json={"theme": "dark"})
    assert put_resp.status_code == 401


async def test_preferences_are_per_user(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """One user's preferences do not leak into another user's."""
    put = await client.put(
        "/v1/users/me/preferences",
        json={"theme": "dark"},
        headers=auth_headers_user_a,
    )
    assert put.status_code == 200

    other = await client.get("/v1/users/me/preferences", headers=auth_headers_user_b)
    assert other.status_code == 200
    assert other.json()["preferences"] == {}
