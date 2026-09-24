"""
Integration tests for share permission management (owner-side PATCH) and the
safe inline preview endpoint.

Covers:
- ShareResponse exposes download_allowed; create persists View Only vs
  View + Download grants.
- Owner can change an existing share's permission (PATCH); recipient's
  access follows immediately.
- Preview endpoint: 200 + inline semantics for recipients (both levels),
  owner, and 404 for outsiders; write attempts stay 403; version downloads
  follow the share's download grant.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from vaultdocs.models.user import User

pytestmark = pytest.mark.asyncio


async def _create_document(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/v1/documents", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _upload_file(
    client: AsyncClient,
    headers: dict[str, str],
    document_id: str,
    filename: str,
    content: bytes,
) -> str:
    response = await client.post(
        f"/v1/documents/{document_id}/upload",
        files={"file": (filename, content, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["file_path"]


async def _share(
    client: AsyncClient,
    owner_headers: dict[str, str],
    document_id: str,
    recipient_email: str,
    *,
    download_allowed: bool,
) -> dict:
    response = await client.post(
        f"/v1/documents/{document_id}/shares",
        json={"user_email": recipient_email, "download_allowed": download_allowed},
        headers=owner_headers,
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# ShareResponse exposes download_allowed; create persists the grant
# ---------------------------------------------------------------------------


async def test_share_response_reports_download_allowed_true(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Creating a View + Download share persists and reports the grant."""
    doc_id = await _create_document(client, auth_headers_user_a, "Share DL True")
    share = await _share(
        client,
        auth_headers_user_a,
        doc_id,
        user_b.email,
        download_allowed=True,
    )
    assert share["download_allowed"] is True


async def test_share_response_reports_download_allowed_false(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Creating a View Only share persists download_allowed=false."""
    doc_id = await _create_document(client, auth_headers_user_a, "Share DL False")
    share = await _share(
        client,
        auth_headers_user_a,
        doc_id,
        user_b.email,
        download_allowed=False,
    )
    assert share["download_allowed"] is False


async def test_share_list_reports_each_share_permission(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """GET /shares reflects each share's stored download grant."""
    doc_id = await _create_document(client, auth_headers_user_a, "Share List Perms")
    await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False)

    listing = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_a)
    assert listing.status_code == 200
    shares = listing.json()
    assert len(shares) == 1
    assert shares[0]["download_allowed"] is False


# ---------------------------------------------------------------------------
# PATCH share permission
# ---------------------------------------------------------------------------


async def test_owner_can_change_share_to_view_plus_download(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Owner upgrades a View Only share; recipient can download afterwards."""
    doc_id = await _create_document(client, auth_headers_user_a, "Upgrade Share Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "up.txt", b"up content")
    share = await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False)

    # View-only: download blocked.
    blocked = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert blocked.status_code == 403

    patch = await client.patch(
        f"/v1/documents/{doc_id}/shares/{share['id']}",
        json={"download_allowed": True},
        headers=auth_headers_user_a,
    )
    assert patch.status_code == 200
    assert patch.json()["download_allowed"] is True

    # Recipient can download now.
    allowed = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert allowed.status_code == 200

    Path(path).unlink()


async def test_owner_can_downgrade_share_to_view_only(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Owner downgrades a View + Download share; downloads 403 immediately."""
    doc_id = await _create_document(client, auth_headers_user_a, "Downgrade Share Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "down.txt", b"down")
    share = await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=True)

    patch = await client.patch(
        f"/v1/documents/{doc_id}/shares/{share['id']}",
        json={"download_allowed": False},
        headers=auth_headers_user_a,
    )
    assert patch.status_code == 200
    assert patch.json()["download_allowed"] is False

    blocked = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert blocked.status_code == 403

    # Version download blocked too.
    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    version_id = versions.json()[0]["id"]
    vblocked = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}/download",
        headers=auth_headers_user_b,
    )
    assert vblocked.status_code == 403

    Path(path).unlink()


async def test_non_owner_cannot_change_share_permission(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Recipient cannot PATCH a share (owner-only, clean 403)."""
    doc_id = await _create_document(client, auth_headers_user_a, "No Patch Share")
    share = await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False)

    patch = await client.patch(
        f"/v1/documents/{doc_id}/shares/{share['id']}",
        json={"download_allowed": True},
        headers=auth_headers_user_b,
    )
    assert patch.status_code == 403

    # Grant unchanged.
    check = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_a)
    assert check.json()[0]["download_allowed"] is False


async def test_patch_nonexistent_share_returns_404(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """PATCH on a share that does not belong to the doc returns 404."""
    from uuid import uuid4

    doc_id = await _create_document(client, auth_headers_user_a, "Patch 404 Doc")

    resp = await client.patch(
        f"/v1/documents/{doc_id}/shares/{uuid4()}",
        json={"download_allowed": True},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Safe inline preview endpoint
# ---------------------------------------------------------------------------


async def test_owner_can_preview(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Owner streams the file inline with preview semantics."""
    doc_id = await _create_document(client, auth_headers_user_a, "Owner Preview")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "note.txt", b"preview me")

    resp = await client.get(f"/v1/documents/{doc_id}/preview", headers=auth_headers_user_a)
    assert resp.status_code == 200
    assert resp.content == b"preview me"
    assert resp.headers["content-type"].startswith("text/plain")
    assert "attachment" not in resp.headers.get("content-disposition", "")

    Path(path).unlink()


async def test_view_only_recipient_can_preview(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """View-only (seen) recipient: preview 200 while downloads stay 403."""
    doc_id = await _create_document(client, auth_headers_user_a, "Viewer Preview")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "seen.txt", b"seen content")
    await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False)

    preview = await client.get(f"/v1/documents/{doc_id}/preview", headers=auth_headers_user_b)
    assert preview.status_code == 200
    assert preview.content == b"seen content"
    assert "attachment" not in preview.headers.get("content-disposition", "")

    download = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert download.status_code == 403

    Path(path).unlink()


async def test_download_recipient_can_preview_and_download(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """View + Download recipient: preview 200 AND attachment download 200."""
    doc_id = await _create_document(client, auth_headers_user_a, "DL Recipient Preview")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "both.txt", b"both content")
    await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=True)

    preview = await client.get(f"/v1/documents/{doc_id}/preview", headers=auth_headers_user_b)
    assert preview.status_code == 200

    download = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert download.status_code == 200
    assert download.content == b"both content"
    assert "attachment" in download.headers.get("content-disposition", "")

    Path(path).unlink()


async def test_outsider_cannot_preview(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """Outsider gets safe 404 on preview (existence not disclosed)."""
    doc_id = await _create_document(client, auth_headers_user_a, "Stranger Preview")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "hidden.txt", b"hidden")

    resp = await client.get(f"/v1/documents/{doc_id}/preview", headers=auth_headers_user_b)
    assert resp.status_code == 404

    Path(path).unlink()


async def test_preview_unsupported_type_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Unsupported binary type gets 400 'preview unavailable', not a download."""
    doc_id = await _create_document(client, auth_headers_user_a, "Bad Preview Type")

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("blob.bin", b"\x00\x01\x02\x03", "application/octet-stream")},
        headers=auth_headers_user_a,
    )
    assert upload.status_code == 200
    path = upload.json()["file_path"]

    resp = await client.get(f"/v1/documents/{doc_id}/preview", headers=auth_headers_user_a)
    assert resp.status_code == 400
    assert "preview" in resp.json()["detail"].lower()

    Path(path).unlink()


async def test_preview_requires_auth(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Unauthenticated preview is rejected with 401."""
    doc_id = await _create_document(client, auth_headers_user_a, "Unauth Preview")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "u.txt", b"u")

    resp = await client.get(f"/v1/documents/{doc_id}/preview")
    assert resp.status_code == 401

    Path(path).unlink()
