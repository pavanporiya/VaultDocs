"""
Integration tests for the "shared with me" listing endpoint:
GET /v1/documents/shared
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_document(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/v1/documents", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _share_document(
    client: AsyncClient,
    owner_headers: dict[str, str],
    document_id: str,
    recipient_email: str,
) -> None:
    response = await client.post(
        f"/v1/documents/{document_id}/shares",
        json={"user_email": recipient_email},
        headers=owner_headers,
    )
    assert response.status_code == 201


async def test_shared_with_me_lists_shared_documents(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_a,
    user_b,
) -> None:
    """Recipient sees documents shared with them, with owner context."""
    doc_id = await _create_document(client, auth_headers_user_a, "Shared With Me Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert resp.status_code == 200

    docs = resp.json()
    ids = [d["id"] for d in docs]
    assert doc_id in ids

    shared = next(d for d in docs if d["id"] == doc_id)
    assert shared["name"] == "Shared With Me Doc"
    assert shared["owner_id"] == str(user_a.id)
    assert shared["shared_by_name"] == "User A"
    assert shared["shared_by_email"] == user_a.email
    assert shared["shared_at"] is not None
    # file_path must never leak to recipients
    assert shared["file_path"] is None


async def test_shared_with_me_excludes_own_documents(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Own documents do not appear in the shared-with-me list."""
    await _create_document(client, auth_headers_user_a, "My Own Doc")

    resp = await client.get("/v1/documents/shared", headers=auth_headers_user_a)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_shared_with_me_empty_for_user_without_shares(
    client: AsyncClient,
    auth_headers_user_b: dict[str, str],
) -> None:
    """User with no shares gets an empty list."""
    resp = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_shared_with_me_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated access is rejected."""
    resp = await client.get("/v1/documents/shared")
    assert resp.status_code == 401


async def test_shared_with_me_multiple_documents(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Multiple shared documents are all listed."""
    doc_1 = await _create_document(client, auth_headers_user_a, "Shared One")
    doc_2 = await _create_document(client, auth_headers_user_a, "Shared Two")
    await _share_document(client, auth_headers_user_a, doc_1, user_b.email)
    await _share_document(client, auth_headers_user_a, doc_2, user_b.email)

    resp = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert doc_1 in ids
    assert doc_2 in ids


async def test_revoked_share_disappears_from_shared_with_me(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Revoking a share removes the document from the recipient's list."""
    doc_id = await _create_document(client, auth_headers_user_a, "Revoked Shared Doc")

    create = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert create.status_code == 201
    share_id = create.json()["id"]

    before = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert doc_id in [d["id"] for d in before.json()]

    revoke = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}",
        headers=auth_headers_user_a,
    )
    assert revoke.status_code == 204

    after = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert doc_id not in [d["id"] for d in after.json()]


async def test_shared_with_me_document_still_readable_and_downloadable(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Documents listed via /shared remain readable and downloadable."""
    doc_id = await _create_document(client, auth_headers_user_a, "Download Shared Doc")

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("hello.txt", b"hello shared world", "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload.status_code in (200, 201)

    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    listed = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert doc_id in [d["id"] for d in listed.json()]

    read = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert read.status_code == 200

    download = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert download.status_code == 200
