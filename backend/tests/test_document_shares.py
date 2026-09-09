"""
Integration tests for document sharing: owner-side management and
shared-user read-only access.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from vaultdocs.models.user import User

pytestmark = pytest.mark.asyncio


async def _create_document(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/v1/documents", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _register_user(client: AsyncClient, email: str) -> dict[str, str]:
    register = await client.post(
        "/v1/auth/register",
        json={"full_name": "Recipient", "email": email, "password": "Password123!"},
    )
    assert register.status_code in (200, 201)
    login = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _share_document(
    client: AsyncClient,
    owner_headers: dict[str, str],
    document_id: str,
    recipient_email: str,
) -> str:
    response = await client.post(
        f"/v1/documents/{document_id}/shares",
        json={"user_email": recipient_email},
        headers=owner_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Owner-side share management
# ---------------------------------------------------------------------------


async def test_owner_can_create_share(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Owner can share a document with another registered user."""
    doc_id = await _create_document(client, auth_headers_user_a, "Shared Doc")

    resp = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_id"] == doc_id
    assert data["shared_with_user_id"] == str(user_b.id)
    assert "id" in data
    assert "created_at" in data


async def test_share_requires_recipient_to_exist(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Sharing with a non-existent user fails with 400."""
    doc_id = await _create_document(client, auth_headers_user_a, "Doc No Recipient")

    resp = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": "ghost@example.com"},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 400


async def test_duplicate_share_prevented(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_b,
) -> None:
    """Sharing the same document twice with the same user fails with 400."""
    doc_id = await _create_document(client, auth_headers_user_a, "Dup Share Doc")

    first = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert second.status_code == 400


async def test_self_share_prevented(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a,
) -> None:
    """Owner cannot share a document with themselves."""
    doc_id = await _create_document(client, auth_headers_user_a, "Self Share Doc")

    resp = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_a.email},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 400


async def test_non_owner_cannot_create_share(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Non-owner cannot share someone else's document (safe 404)."""
    doc_id = await _create_document(client, auth_headers_user_a, "Private Doc")

    resp = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404


async def test_owner_can_list_shares(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_b,
) -> None:
    """Owner can list shares for their document."""
    doc_id = await _create_document(client, auth_headers_user_a, "List Shares Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get(
        f"/v1/documents/{doc_id}/shares",
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 200
    shares = resp.json()
    assert len(shares) == 1
    assert shares[0]["shared_with_user_id"] == str(user_b.id)


async def test_non_owner_cannot_list_shares(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Non-owner cannot list shares for someone else's document (safe 404)."""
    doc_id = await _create_document(client, auth_headers_user_a, "Hidden Shares Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get(
        f"/v1/documents/{doc_id}/shares",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404


async def test_owner_can_revoke_share(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Owner can revoke a share; recipient loses access."""
    doc_id = await _create_document(client, auth_headers_user_a, "Revoke Doc")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    # Recipient has access before revocation
    before = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert before.status_code == 200

    resp = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}",
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 204

    # Recipient loses access after revocation
    after = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert after.status_code == 404


async def test_revoke_nonexistent_share_fails(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Revoking a non-existent share returns 404."""
    doc_id = await _create_document(client, auth_headers_user_a, "No Share Doc")

    resp = await client.delete(
        f"/v1/documents/{doc_id}/shares/{uuid4()}",
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 404


async def test_non_owner_cannot_revoke_share(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Recipient (or any non-owner) cannot revoke a share (safe 404)."""
    doc_id = await _create_document(client, auth_headers_user_a, "No Revoke Doc")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404


async def test_share_endpoints_unauthenticated_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Unauthenticated access to share endpoints is rejected with 401."""
    doc_id = await _create_document(client, auth_headers_user_a, "Unauth Share Doc")

    create_resp = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": "x@example.com"},
    )
    assert create_resp.status_code == 401

    list_resp = await client.get(f"/v1/documents/{doc_id}/shares")
    assert list_resp.status_code == 401

    del_resp = await client.delete(f"/v1/documents/{doc_id}/shares/{uuid4()}")
    assert del_resp.status_code == 401


# ---------------------------------------------------------------------------
# Shared-user read-only document access (Task 2)
# ---------------------------------------------------------------------------


async def test_shared_user_can_read_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Shared recipient can retrieve the document metadata."""
    doc_id = await _create_document(client, auth_headers_user_a, "Readable Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == doc_id
    assert data["name"] == "Readable Doc"
    assert data["owner_id"] == str(
        (await client.get("/v1/documents", headers=auth_headers_user_a)).json()[0]["owner_id"]
    )


async def test_shared_user_cannot_update_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Shared recipient cannot rename or move the document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Locked Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    rename = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Hijacked Name"},
        headers=auth_headers_user_b,
    )
    assert rename.status_code == 404

    move = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"folder_id": None},
        headers=auth_headers_user_b,
    )
    assert move.status_code == 404

    # Name unchanged
    check = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert check.json()["name"] == "Locked Doc"


async def test_shared_user_cannot_delete_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Shared recipient cannot delete the document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Survivor Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.delete(
        f"/v1/documents/{doc_id}",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404

    still_there = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert still_there.status_code == 200


async def test_shared_user_cannot_upload(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Shared recipient cannot upload or replace the file."""
    doc_id = await _create_document(client, auth_headers_user_a, "No Upload Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("evil.txt", b"malicious", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404

    replace = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("evil2.txt", b"malicious", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert replace.status_code == 404


async def test_shared_user_cannot_manage_shares(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Shared recipient cannot create, list, or revoke shares."""
    doc_id = await _create_document(client, auth_headers_user_a, "Share Mgmt Doc")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    create = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": "someoneelse@example.com"},
        headers=auth_headers_user_b,
    )
    assert create.status_code == 404

    listing = await client.get(
        f"/v1/documents/{doc_id}/shares",
        headers=auth_headers_user_b,
    )
    assert listing.status_code == 404

    revoke = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}",
        headers=auth_headers_user_b,
    )
    assert revoke.status_code == 404


async def test_unshared_user_cannot_access_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """User without a share cannot access the document (safe 404)."""
    doc_id = await _create_document(client, auth_headers_user_a, "Secret Doc")

    resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found."


async def test_unauthenticated_cannot_access_shared_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_b,
) -> None:
    """Unauthenticated user cannot access a shared document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Unauth Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get(f"/v1/documents/{doc_id}")
    assert resp.status_code == 401


async def test_owner_permissions_unchanged_after_share(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_b,
) -> None:
    """Owner retains full access after sharing."""
    doc_id = await _create_document(client, auth_headers_user_a, "Owner Keep Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    get_resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert get_resp.status_code == 200

    patch_resp = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Owner Renamed"},
        headers=auth_headers_user_a,
    )
    assert patch_resp.status_code == 200

    delete_resp = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert delete_resp.status_code == 204


async def test_shared_document_not_in_recipient_list(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Shared documents do not leak into the recipient's own document list."""
    doc_id = await _create_document(client, auth_headers_user_a, "Not Mine Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get("/v1/documents", headers=auth_headers_user_b)
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert doc_id not in ids


async def test_shared_document_not_in_recipient_search(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Search cannot be used to discover documents shared with you."""
    doc_id = await _create_document(client, auth_headers_user_a, "Searchable Shared Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get(
        "/v1/documents/search",
        params={"q": "Searchable Shared"},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert doc_id not in ids


async def test_revoked_user_cannot_access_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Revoked recipient immediately loses read access."""
    doc_id = await _create_document(client, auth_headers_user_a, "Revoke Access Doc")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    before = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert before.status_code == 200

    revoke = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}",
        headers=auth_headers_user_a,
    )
    assert revoke.status_code == 204

    after = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert after.status_code == 404
