"""
Security regression tests (Task 4): authentication walls and recipient isolation.
"""

import pytest
from httpx import AsyncClient

from vaultdocs.models.user import User

pytestmark = pytest.mark.asyncio


async def test_unauthenticated_folder_access_rejected(client: AsyncClient) -> None:
    """Unauthenticated access to folder endpoints is rejected with 401."""
    post_resp = await client.post("/v1/folders", json={"name": "Unauth Folder"})
    assert post_resp.status_code == 401

    list_resp = await client.get("/v1/folders")
    assert list_resp.status_code == 401

    get_resp = await client.get("/v1/folders/00000000-0000-0000-0000-000000000000")
    assert get_resp.status_code == 401

    patch_resp = await client.patch(
        "/v1/folders/00000000-0000-0000-0000-000000000000",
        json={"name": "Hijacked"},
    )
    assert patch_resp.status_code == 401

    del_resp = await client.delete("/v1/folders/00000000-0000-0000-0000-000000000000")
    assert del_resp.status_code == 401


async def test_unauthenticated_search_rejected(client: AsyncClient) -> None:
    """Unauthenticated access to search is rejected with 401."""
    resp = await client.get("/v1/documents/search", params={"q": "anything"})
    assert resp.status_code == 401


async def test_shared_user_cannot_access_owners_other_documents(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """
    Recipient isolation: sharing one document does not grant access to the
    owner's other (unshared) documents.
    """
    shared_resp = await client.post(
        "/v1/documents",
        json={"name": "Shared One"},
        headers=auth_headers_user_a,
    )
    shared_id = shared_resp.json()["id"]

    private_resp = await client.post(
        "/v1/documents",
        json={"name": "Private Two"},
        headers=auth_headers_user_a,
    )
    private_id = private_resp.json()["id"]

    private_upload = await client.post(
        f"/v1/documents/{private_id}/upload",
        files={"file": ("private_two.txt", b"private two bytes", "text/plain")},
        headers=auth_headers_user_a,
    )
    private_file_path = private_upload.json()["file_path"]

    share_resp = await client.post(
        f"/v1/documents/{shared_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    assert share_resp.status_code == 201

    # Recipient CAN read the shared document
    ok = await client.get(f"/v1/documents/{shared_id}", headers=auth_headers_user_b)
    assert ok.status_code == 200

    # Recipient CANNOT read/download the owner's other document
    read = await client.get(f"/v1/documents/{private_id}", headers=auth_headers_user_b)
    assert read.status_code == 404

    download = await client.get(
        f"/v1/documents/{private_id}/download", headers=auth_headers_user_b
    )
    assert download.status_code == 404

    versions = await client.get(
        f"/v1/documents/{private_id}/versions", headers=auth_headers_user_b
    )
    assert versions.status_code == 404

    # Recipient cannot discover private doc via search even knowing its name
    search = await client.get(
        "/v1/documents/search",
        params={"q": "Private Two"},
        headers=auth_headers_user_b,
    )
    assert search.status_code == 200
    assert private_id not in [d["id"] for d in search.json()]

    # Recipient cannot revoke their own share to grief, nor share private doc
    shares_seen = await client.get(
        f"/v1/documents/{shared_id}/shares", headers=auth_headers_user_b
    )
    assert shares_seen.status_code == 404

    from pathlib import Path

    Path(private_file_path).unlink()


async def test_invalid_token_rejected(client: AsyncClient) -> None:
    """Garbage or tampered bearer tokens are rejected with 401."""
    for token in ("garbage.token.value", "a.b.c"):
        resp = await client.get(
            "/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


async def test_non_owner_cannot_revoke_via_other_document_id(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """
    IDOR: share IDs are namespaced per document — a share of doc A cannot be
    revoked (or referenced) through doc B, even by the doc B owner.
    """
    doc_a_resp = await client.post(
        "/v1/documents",
        json={"name": "Doc A"},
        headers=auth_headers_user_a,
    )
    doc_a_id = doc_a_resp.json()["id"]

    doc_b_resp = await client.post(
        "/v1/documents",
        json={"name": "Doc B"},
        headers=auth_headers_user_b,
    )
    doc_b_id = doc_b_resp.json()["id"]

    share_resp = await client.post(
        f"/v1/documents/{doc_a_id}/shares",
        json={"user_email": user_b.email},
        headers=auth_headers_user_a,
    )
    share_id = share_resp.json()["id"]

    # User B owns doc_b but the share belongs to doc_a: cross-document
    # revocation must fail with 404.
    cross = await client.delete(
        f"/v1/documents/{doc_b_id}/shares/{share_id}",
        headers=auth_headers_user_b,
    )
    assert cross.status_code == 404

    # Share still intact: recipient still has access.
    still = await client.get(f"/v1/documents/{doc_a_id}", headers=auth_headers_user_b)
    assert still.status_code == 200
