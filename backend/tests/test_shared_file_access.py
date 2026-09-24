"""
Integration tests for shared-user file and version access (Task 3).
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


async def _revoke_document(
    client: AsyncClient,
    owner_headers: dict[str, str],
    document_id: str,
    share_id: str,
) -> None:
    response = await client.delete(
        f"/v1/documents/{document_id}/shares/{share_id}",
        headers=owner_headers,
    )
    assert response.status_code == 204


async def _setup_shared_doc_with_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
    name: str,
) -> tuple[str, list[Path]]:
    """Create owner doc, upload two files (2 versions), share with user B."""
    doc_id = await _create_document(client, auth_headers_user_a, name)

    v1_content = b"version one content"
    upload1 = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("v1.txt", v1_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload1.status_code == 200
    v1_path = Path(upload1.json()["file_path"])

    v2_content = b"version two content"
    upload2 = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("v2.txt", v2_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload2.status_code == 200
    v2_path = Path(upload2.json()["file_path"])

    await _share_document(client, auth_headers_user_a, doc_id, user_b.email)
    return doc_id, [v1_path, v2_path]


# ---------------------------------------------------------------------------
# Shared read access: current file
# ---------------------------------------------------------------------------


async def test_shared_user_can_download_current_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient can download the current document file."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "DL Doc"
    )

    resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 200
    assert resp.content == b"version two content"

    for p in paths:
        p.unlink()


async def test_unshared_user_cannot_download_current_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """User without a share cannot download (safe 404)."""
    doc_id = await _create_document(client, auth_headers_user_a, "No Share DL")

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("secret.txt", b"secret content", "text/plain")},
        headers=auth_headers_user_a,
    )
    path = Path(upload.json()["file_path"])

    resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found."

    path.unlink()


async def test_revoked_user_cannot_download_current_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Revoked recipient immediately loses download access."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Revoke DL"
    )

    # List shares to get share id
    shares = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_a)
    share_id = shares.json()[0]["id"]

    before = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert before.status_code == 200

    await _revoke_document(client, auth_headers_user_a, doc_id, share_id)

    after = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_b)
    assert after.status_code == 404

    for p in paths:
        p.unlink()


async def test_unauthenticated_cannot_download_shared_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Unauthenticated download of a shared document is rejected with 401."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Unauth DL"
    )

    resp = await client.get(f"/v1/documents/{doc_id}/download")
    assert resp.status_code == 401

    for p in paths:
        p.unlink()


# ---------------------------------------------------------------------------
# Shared read access: versions
# ---------------------------------------------------------------------------


async def test_shared_user_can_list_versions(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient can list accessible versions, newest first."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Ver List Doc"
    )

    resp = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1

    for p in paths:
        p.unlink()


async def test_shared_user_can_get_version_details(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient can retrieve details of a specific version."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Ver Detail Doc"
    )

    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    version_id = versions.json()[1]["id"]  # version 1

    resp = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == version_id
    assert data["version_number"] == 1
    assert data["original_filename"] == "v1.txt"

    for p in paths:
        p.unlink()


async def test_shared_user_can_download_version_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient can download a specific version's file."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Ver DL Doc"
    )

    versions = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    version_id = versions.json()[1]["id"]  # version 1

    resp = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}/download",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 200
    assert resp.content == b"version one content"

    for p in paths:
        p.unlink()


async def test_unshared_user_cannot_list_versions(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """User without a share cannot list versions (safe 404)."""
    doc_id = await _create_document(client, auth_headers_user_a, "No Share Vers")

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("only.txt", b"only content", "text/plain")},
        headers=auth_headers_user_a,
    )
    path = Path(upload.json()["file_path"])

    resp = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    assert resp.status_code == 404

    path.unlink()


async def test_revoked_user_cannot_access_versions(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Revoked recipient loses version list + download access."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Revoke Vers"
    )

    shares = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_a)
    share_id = shares.json()[0]["id"]

    version_list = await client.get(
        f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b
    )
    assert version_list.status_code == 200
    version_id = version_list.json()[0]["id"]

    await _revoke_document(client, auth_headers_user_a, doc_id, share_id)

    list_after = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_b)
    assert list_after.status_code == 404

    dl_after = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}/download",
        headers=auth_headers_user_b,
    )
    assert dl_after.status_code == 404

    for p in paths:
        p.unlink()


async def test_unauthenticated_cannot_list_shared_versions(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Unauthenticated version access is rejected with 401."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Unauth Vers"
    )

    resp = await client.get(f"/v1/documents/{doc_id}/versions")
    assert resp.status_code == 401

    for p in paths:
        p.unlink()


async def test_shared_user_cannot_access_nonexistent_version(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient gets 404 for a version that does not belong to the doc."""
    from uuid import uuid4

    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Wrong Ver Doc"
    )

    resp = await client.get(
        f"/v1/documents/{doc_id}/versions/{uuid4()}/download",
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Version not found."

    for p in paths:
        p.unlink()


# ---------------------------------------------------------------------------
# Owner unchanged + shared-user write restrictions on file/version endpoints
# ---------------------------------------------------------------------------


async def test_owner_still_has_full_file_and_version_access(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Owner retains full download/version access after sharing."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "Owner Keep DL"
    )

    dl = await client.get(f"/v1/documents/{doc_id}/download", headers=auth_headers_user_a)
    assert dl.status_code == 200
    assert dl.content == b"version two content"

    vers = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_a)
    assert vers.status_code == 200
    assert len(vers.json()) == 2

    for p in paths:
        p.unlink()


async def test_shared_user_cannot_upload_or_replace(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient cannot create new versions via upload/replace."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "No Write Vers"
    )

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("hacked.txt", b"hacked content", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert upload.status_code == 403

    replace = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("hacked2.txt", b"hacked content", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert replace.status_code == 403

    # No new version created
    vers = await client.get(f"/v1/documents/{doc_id}/versions", headers=auth_headers_user_a)
    assert len(vers.json()) == 2

    for p in paths:
        p.unlink()


async def test_shared_user_cannot_delete_document_or_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient cannot delete the document; files stay intact."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "No Delete Vers"
    )

    delete = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers_user_b)
    assert delete.status_code == 403

    for p in paths:
        assert p.exists()
        p.unlink()


async def test_shared_user_cannot_rename_or_move(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient cannot modify document metadata."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "No Meta Doc"
    )

    rename = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Renamed By Shared"},
        headers=auth_headers_user_b,
    )
    assert rename.status_code == 403

    check = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert check.json()["name"] == "No Meta Doc"

    for p in paths:
        p.unlink()


async def test_shared_user_cannot_manage_shares_on_file_doc(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b: User,
) -> None:
    """Shared recipient cannot create or revoke shares on the shared document."""
    doc_id, paths = await _setup_shared_doc_with_file(
        client, auth_headers_user_a, auth_headers_user_b, user_b, "No Share Mgmt"
    )

    create = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": "other@example.com"},
        headers=auth_headers_user_b,
    )
    assert create.status_code == 403

    shares = await client.get(f"/v1/documents/{doc_id}/shares", headers=auth_headers_user_b)
    assert shares.status_code == 403

    for p in paths:
        p.unlink()


async def test_idor_user_b_cannot_guess_user_a_private_doc(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """User B cannot gain access to User A's private doc by guessing IDs."""
    doc_id = await _create_document(client, auth_headers_user_a, "Guess Proof")

    upload = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("private.txt", b"private bytes", "text/plain")},
        headers=auth_headers_user_a,
    )
    path = Path(upload.json()["file_path"])

    for endpoint in (
        f"/v1/documents/{doc_id}",
        f"/v1/documents/{doc_id}/download",
        f"/v1/documents/{doc_id}/versions",
    ):
        resp = await client.get(endpoint, headers=auth_headers_user_b)
        assert resp.status_code == 404

    path.unlink()
