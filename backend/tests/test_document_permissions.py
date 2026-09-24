"""
Integration tests for the RBAC permission contract (view-only / "seen" enforcement).

Covers:
- Authorization flags on GET /v1/documents/{id} (owner vs. share recipient).
- Viewer write attempts -> clean 403 Forbidden (not misleading 404/500).
- View-only (seen) share download blocking with 403 (current + version files).
- Owner-only share management with 403 for recipients.
- Owner flows remain fully intact.
"""

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
    """Upload a file and return its on-disk path for cleanup."""
    response = await client.post(
        f"/v1/documents/{document_id}/upload",
        files={"file": (filename, content, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["file_path"]


async def _share_document(
    client: AsyncClient,
    owner_headers: dict[str, str],
    document_id: str,
    recipient_email: str,
    *,
    download_allowed: bool = True,
) -> str:
    response = await client.post(
        f"/v1/documents/{document_id}/shares",
        json={"user_email": recipient_email, "download_allowed": download_allowed},
        headers=owner_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Authorization flags on document responses
# ---------------------------------------------------------------------------


async def test_owner_gets_owner_permission_flags(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Owner reading their own document gets full authorization flags."""
    doc_id = await _create_document(client, auth_headers_user_a, "Owner Flags Doc")

    resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_owner"] is True
    assert data["permission"] == "owner"
    assert data["can_edit"] is True
    assert data["can_download"] is True
    assert data["can_share"] is True
    assert data["can_delete"] is True


async def test_viewer_gets_viewer_permission_flags(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Share recipient reading a shared document gets view-only flags."""
    doc_id = await _create_document(client, auth_headers_user_a, "Viewer Flags Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_owner"] is False
    assert data["permission"] == "viewer"
    assert data["can_edit"] is False
    assert data["can_share"] is False
    assert data["can_delete"] is False


async def test_shared_with_me_includes_viewer_flags(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """/documents/shared rows carry viewer flags and never leak file paths."""
    doc_id = await _create_document(client, auth_headers_user_a, "Shared Flags Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    assert resp.status_code == 200
    shared = next(d for d in resp.json() if d["id"] == doc_id)
    assert shared["is_owner"] is False
    assert shared["permission"] == "viewer"
    assert shared["can_edit"] is False
    assert shared["can_download"] is True
    assert shared["can_share"] is False
    assert shared["can_delete"] is False
    assert shared["file_path"] is None


# ---------------------------------------------------------------------------
# Viewer write attempts -> clean 403 Forbidden
# ---------------------------------------------------------------------------


async def test_viewer_upload_rejected_with_403(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Viewer cannot POST-upload a file to a shared document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Viewer Upload Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "real.txt", b"real content")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("hacked.txt", b"hacked", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 403

    # No new version was created.
    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_a)
    assert len(versions.json()) == 1

    import pathlib

    pathlib.Path(path).unlink()


async def test_viewer_replace_rejected_with_403(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Viewer cannot PUT-replace the file of a shared document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Viewer Replace Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "real.txt", b"real content")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("hacked.txt", b"hacked", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 403

    import pathlib

    pathlib.Path(path).unlink()


async def test_viewer_patch_rejected_with_403(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Viewer cannot PATCH (rename/move) a shared document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Viewer Patch Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Renamed By Viewer"},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 403

    check = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert check.json()["name"] == "Viewer Patch Doc"


async def test_viewer_delete_rejected_with_403(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Viewer cannot DELETE a shared document."""
    doc_id = await _create_document(client, auth_headers_user_a, "Viewer Delete Doc")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    resp = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert resp.status_code == 403

    still_there = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert still_there.status_code == 200


async def test_outsider_still_gets_safe_404(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """Users WITHOUT a share keep the safe 404 (existence never disclosed)."""
    doc_id = await _create_document(client, auth_headers_user_a, "Outsider Doc")

    read = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert read.status_code == 404

    patch = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Hijack"},
        headers=auth_headers_user_b,
    )
    assert patch.status_code == 404

    delete = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert delete.status_code == 404

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("x.txt", b"x", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert upload.status_code == 404


# ---------------------------------------------------------------------------
# Download permission enforcement (view-only / "seen" shares)
# ---------------------------------------------------------------------------


async def test_download_allowed_share_can_download(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """A share with download grant can download current file and versions."""
    doc_id = await _create_document(client, auth_headers_user_a, "DL Grant Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "v.txt", b"dl content")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=True)

    resp = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert resp.status_code == 200
    assert resp.content == b"dl content"

    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    version_id = versions.json()[0]["id"]
    vresp = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}/download",
        headers=auth_headers_user_b,
    )
    assert vresp.status_code == 200

    import pathlib

    pathlib.Path(path).unlink()


async def test_view_only_share_download_blocked_with_403(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Strictly view-only (seen) share blocks attachment downloads with 403."""
    doc_id = await _create_document(client, auth_headers_user_a, "Seen Only Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "seen.txt", b"seen content")
    await _share_document(
        client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False
    )

    resp = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert resp.status_code == 403
    assert "view-only" in resp.json()["detail"].lower()

    # Version file download is blocked too.
    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    assert versions.status_code == 200  # metadata listing stays readable
    version_id = versions.json()[0]["id"]
    vresp = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}/download",
        headers=auth_headers_user_b,
    )
    assert vresp.status_code == 403

    # Owner keeps full download access.
    owner_dl = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_a)
    assert owner_dl.status_code == 200

    import pathlib

    pathlib.Path(path).unlink()


async def test_view_only_share_flags_reflect_no_download(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """GET /documents/{id} reports can_download=false for seen-only shares."""
    doc_id = await _create_document(client, auth_headers_user_a, "Seen Flags Doc")
    await _share_document(
        client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False
    )

    resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_download"] is False
    assert data["permission"] == "viewer"
    assert data["can_edit"] is False

    shared = await client.get("/v1/documents/shared", headers=auth_headers_user_b)
    row = next(d for d in shared.json() if d["id"] == doc_id)
    assert row["can_download"] is False


async def test_revoked_share_download_falls_back_to_404(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Once revoked, the recipient is an outsider again: safe 404 on download."""
    doc_id = await _create_document(client, auth_headers_user_a, "Revoke DL Doc")
    path = await _upload_file(client, auth_headers_user_a, doc_id, "rev.txt", b"rev content")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    revoke = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}", headers=auth_headers_user_a
    )
    assert revoke.status_code == 204

    resp = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert resp.status_code == 404

    import pathlib

    pathlib.Path(path).unlink()


# ---------------------------------------------------------------------------
# Owner-only share management with clean 403 for recipients
# ---------------------------------------------------------------------------


async def test_recipient_share_management_rejected_with_403(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Recipient cannot create/list/revoke shares: clean 403, not 404."""
    doc_id = await _create_document(client, auth_headers_user_a, "Share Mgmt 403 Doc")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    create = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": "someoneelse@example.com"},
        headers=auth_headers_user_b,
    )
    assert create.status_code == 403

    listing = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_b)
    assert listing.status_code == 403

    revoke = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}", headers=auth_headers_user_b
    )
    assert revoke.status_code == 403

    # Owner still sees exactly one share.
    owner_listing = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_a)
    assert len(owner_listing.json()) == 1


async def test_create_view_only_share_via_flag(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Default shares keep download grants (backward compatible)."""
    doc_id = await _create_document(client, auth_headers_user_a, "Default Share Doc")
    share_id = await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    listing = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_a)
    shares = listing.json()
    assert len(shares) == 1
    assert shares[0]["id"] == share_id

    resp = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert resp.json()["can_download"] is True


# ---------------------------------------------------------------------------
# Owner flows remain fully intact
# ---------------------------------------------------------------------------


async def test_owner_full_flow_unaffected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Owner can upload, rename, share, download, and delete as before."""
    doc_id = await _create_document(client, auth_headers_user_a, "Owner Flow Doc")

    path = await _upload_file(client, auth_headers_user_a, doc_id, "flow.txt", b"flow content")
    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)

    patch = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Owner Flow Renamed"},
        headers=auth_headers_user_a,
    )
    assert patch.status_code == 200

    dl = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_a)
    assert dl.status_code == 200
    assert dl.content == b"flow content"

    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_a)
    assert versions.status_code == 200
    assert len(versions.json()) == 1

    delete = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert delete.status_code == 204

    import pathlib

    pathlib.Path(path).unlink(missing_ok=True)
