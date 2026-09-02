"""
Integration tests for document versioning feature.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.core.settings import settings
from vaultdocs.models.document_version import DocumentVersion


@pytest.mark.asyncio
async def test_initial_upload_creates_version_1(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    Verify initial file upload creates version 1.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "V1 Doc"},
        headers=auth_headers_user_a,
    )
    assert create_res.status_code == 201
    doc_id = create_res.json()["id"]

    upload_res = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("initial.txt", b"Initial content", "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload_res.status_code == 200

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["original_filename"] == "initial.txt"
    assert versions[0]["file_size"] == len(b"Initial content")
    assert versions[0]["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_replacement_creates_version_2_and_3(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Verify consecutive replacements create version 2 and version 3.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "V Multi Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]

    # Version 1
    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("file1.txt", b"Version 1 content", "text/plain")},
        headers=auth_headers_user_a,
    )

    # Version 2
    upload_res2 = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("file2.txt", b"Version 2 content", "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload_res2.status_code == 200

    # Version 3
    upload_res3 = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("file3.txt", b"Version 3 content", "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload_res3.status_code == 200

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) == 3
    # Check ordered newest first
    assert [v["version_number"] for v in versions] == [3, 2, 1]
    assert versions[0]["original_filename"] == "file3.txt"
    assert versions[1]["original_filename"] == "file2.txt"
    assert versions[2]["original_filename"] == "file1.txt"


@pytest.mark.asyncio
async def test_version_metadata_and_historical_download(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Verify version details endpoint, version metadata, and download historical content.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "History Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]

    # Upload version 1
    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("old_name.txt", b"Old content", "text/plain")},
        headers=auth_headers_user_a,
    )

    # Upload version 2
    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("new_name.txt", b"New content", "text/plain")},
        headers=auth_headers_user_a,
    )

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    versions = versions_res.json()
    v1_meta = next(v for v in versions if v["version_number"] == 1)
    v2_meta = next(v for v in versions if v["version_number"] == 2)

    # Get single version detail
    detail_res = await client.get(
        f"/v1/documents/{doc_id}/versions/{v1_meta['id']}",
        headers=auth_headers_user_a,
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["original_filename"] == "old_name.txt"

    # Download historical version 1
    dl_v1_res = await client.get(
        f"/v1/documents/{doc_id}/versions/{v1_meta['id']}/download",
        headers=auth_headers_user_a,
    )
    assert dl_v1_res.status_code == 200
    assert dl_v1_res.content == b"Old content"

    # Download latest document
    dl_current_res = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_a,
    )
    assert dl_current_res.status_code == 200
    assert dl_current_res.content == b"New content"

    # Download historical version 2
    dl_v2_res = await client.get(
        f"/v1/documents/{doc_id}/versions/{v2_meta['id']}/download",
        headers=auth_headers_user_a,
    )
    assert dl_v2_res.status_code == 200
    assert dl_v2_res.content == b"New content"


@pytest.mark.asyncio
async def test_old_physical_file_remains_available(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Verify previous file is not deleted from physical disk when replaced.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "Physical File Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]

    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("physical1.txt", b"Physical 1 data", "text/plain")},
        headers=auth_headers_user_a,
    )

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    v1_file_path = versions_res.json()[0]["file_path"]
    v1_path = Path(v1_file_path)
    assert v1_path.exists()

    # Perform replacement
    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("physical2.txt", b"Physical 2 data", "text/plain")},
        headers=auth_headers_user_a,
    )

    # Check v1 physical file still exists on disk
    assert v1_path.exists()
    assert v1_path.read_bytes() == b"Physical 1 data"


@pytest.mark.asyncio
async def test_failed_and_oversized_replacements_do_not_create_versions(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Verify failed/oversized upload attempts do not create invalid or duplicate versions.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "Failed Upload Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]

    # Initial upload -> version 1
    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("valid.txt", b"Valid content", "text/plain")},
        headers=auth_headers_user_a,
    )

    # Oversized upload attempt
    oversized_data = b"X" * (settings.max_upload_size + 1024)
    failed_res = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("big.txt", oversized_data, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert failed_res.status_code == 400

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1


@pytest.mark.asyncio
async def test_unauthenticated_and_cross_user_version_access_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    Verify unauthenticated requests and other users cannot access, list, or download versions.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "Private Version Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]

    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("private.txt", b"Secret data", "text/plain")},
        headers=auth_headers_user_a,
    )

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    version_id = versions_res.json()[0]["id"]

    # 1. Unauthenticated requests
    assert (await client.get(f"/v1/documents/{doc_id}/versions")).status_code == 401
    assert (await client.get(f"/v1/documents/{doc_id}/versions/{version_id}")).status_code == 401
    assert (
        await client.get(f"/v1/documents/{doc_id}/versions/{version_id}/download")
    ).status_code == 401

    # 2. User B access (must return 404 to avoid disclosing existence)
    assert (
        await client.get(
            f"/v1/documents/{doc_id}/versions",
            headers=auth_headers_user_b,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/v1/documents/{doc_id}/versions/{version_id}",
            headers=auth_headers_user_b,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/v1/documents/{doc_id}/versions/{version_id}/download",
            headers=auth_headers_user_b,
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_nonexistent_version_returns_404(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Verify requesting a nonexistent version returns 404.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "Nonexistent Ver Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]
    fake_version_id = str(uuid4())

    assert (
        await client.get(
            f"/v1/documents/{doc_id}/versions/{fake_version_id}",
            headers=auth_headers_user_a,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/v1/documents/{doc_id}/versions/{fake_version_id}/download",
            headers=auth_headers_user_a,
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_path_traversal_version_file_download_prevented(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    Verify version download prevents path traversal attempts escaping storage_dir.
    """
    create_res = await client.post(
        "/v1/documents",
        json={"name": "Traversal Ver Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_res.json()["id"]

    await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("traversal.txt", b"Safe data", "text/plain")},
        headers=auth_headers_user_a,
    )

    versions_res = await client.get(
        f"/v1/documents/{doc_id}/versions",
        headers=auth_headers_user_a,
    )
    version_id = versions_res.json()[0]["id"]

    # Manually tamper with file_path in database to attempt path traversal
    result = await db_session.execute(
        select(DocumentVersion).where(DocumentVersion.id == version_id)
    )
    version_obj = result.scalar_one()
    version_obj.file_path = "/etc/passwd"
    await db_session.commit()

    dl_res = await client.get(
        f"/v1/documents/{doc_id}/versions/{version_id}/download",
        headers=auth_headers_user_a,
    )
    assert dl_res.status_code == 404
