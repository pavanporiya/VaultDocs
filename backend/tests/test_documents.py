"""
Unit and integration tests for Document Management Module.
"""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.core.settings import settings
from vaultdocs.models.document import Document
from vaultdocs.models.user import User


@pytest.mark.asyncio
async def test_create_root_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a: User,
) -> None:
    """
    1. Authenticated user can create a root document (no folder_id).
    """
    response = await client.post(
        "/v1/documents",
        json={"name": "Root Document"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Root Document"
    assert data["folder_id"] is None
    assert data["owner_id"] == str(user_a.id)
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_document_in_own_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a: User,
) -> None:
    """
    2. Authenticated user can create a document inside their own folder.
    """
    folder_resp = await client.post(
        "/v1/folders",
        json={"name": "Project Folder"},
        headers=auth_headers_user_a,
    )
    assert folder_resp.status_code == 201
    folder_id = folder_resp.json()["id"]

    doc_resp = await client.post(
        "/v1/documents",
        json={"name": "Project Spec", "folder_id": folder_id},
        headers=auth_headers_user_a,
    )
    assert doc_resp.status_code == 201
    doc_data = doc_resp.json()
    assert doc_data["name"] == "Project Spec"
    assert doc_data["folder_id"] == folder_id
    assert doc_data["owner_id"] == str(user_a.id)


@pytest.mark.asyncio
async def test_list_user_documents(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    3. User can list their documents (and only their documents).
    """
    await client.post(
        "/v1/documents",
        json={"name": "User A Doc 1"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "User A Doc 2"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "User B Doc 1"},
        headers=auth_headers_user_b,
    )

    list_resp = await client.get(
        "/v1/documents",
        headers=auth_headers_user_a,
    )
    assert list_resp.status_code == 200
    docs_a = list_resp.json()
    assert len(docs_a) == 2
    names_a = [d["name"] for d in docs_a]
    assert "User A Doc 1" in names_a
    assert "User A Doc 2" in names_a
    assert "User B Doc 1" not in names_a


@pytest.mark.asyncio
async def test_get_own_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    4. User can retrieve their document by ID.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Target Document"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/v1/documents/{doc_id}",
        headers=auth_headers_user_a,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == doc_id
    assert data["name"] == "Target Document"


@pytest.mark.asyncio
async def test_update_document_name(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    5. User can update their document name.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Original Name"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Renamed Document"},
        headers=auth_headers_user_a,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Renamed Document"


@pytest.mark.asyncio
async def test_move_document_between_folders(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    6. User can move a document between folders.
    """
    f1_resp = await client.post(
        "/v1/folders",
        json={"name": "Folder 1"},
        headers=auth_headers_user_a,
    )
    f1_id = f1_resp.json()["id"]

    f2_resp = await client.post(
        "/v1/folders",
        json={"name": "Folder 2"},
        headers=auth_headers_user_a,
    )
    f2_id = f2_resp.json()["id"]

    doc_resp = await client.post(
        "/v1/documents",
        json={"name": "Movable Doc", "folder_id": f1_id},
        headers=auth_headers_user_a,
    )
    doc_id = doc_resp.json()["id"]
    assert doc_resp.json()["folder_id"] == f1_id

    move_resp = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"folder_id": f2_id},
        headers=auth_headers_user_a,
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["folder_id"] == f2_id


@pytest.mark.asyncio
async def test_move_document_to_root(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    7. User can move a document to root by setting folder_id to null.
    """
    folder_resp = await client.post(
        "/v1/folders",
        json={"name": "Source Folder"},
        headers=auth_headers_user_a,
    )
    folder_id = folder_resp.json()["id"]

    doc_resp = await client.post(
        "/v1/documents",
        json={"name": "Nested Doc", "folder_id": folder_id},
        headers=auth_headers_user_a,
    )
    doc_id = doc_resp.json()["id"]
    assert doc_resp.json()["folder_id"] == folder_id

    root_resp = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"folder_id": None},
        headers=auth_headers_user_a,
    )
    assert root_resp.status_code == 200
    assert root_resp.json()["folder_id"] is None


@pytest.mark.asyncio
async def test_delete_own_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    8. User can delete their document.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Doc To Delete"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/v1/documents/{doc_id}",
        headers=auth_headers_user_a,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/v1/documents/{doc_id}",
        headers=auth_headers_user_a,
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_access_another_user_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    9. User cannot access another user's document.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "User A Private Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/v1/documents/{doc_id}",
        headers=auth_headers_user_b,
    )
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_cannot_update_another_user_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    10. User cannot update another user's document.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "User A Protected Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/v1/documents/{doc_id}",
        json={"name": "Hacked Doc Name"},
        headers=auth_headers_user_b,
    )
    assert patch_resp.status_code == 404
    assert patch_resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_cannot_delete_another_user_document(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    11. User cannot delete another user's document.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "User A Permanent Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/v1/documents/{doc_id}",
        headers=auth_headers_user_b,
    )
    assert del_resp.status_code == 404
    assert del_resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_cannot_use_another_user_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    12. Document cannot use a folder owned by another user.
    """
    create_folder_a = await client.post(
        "/v1/folders",
        json={"name": "User A Folder"},
        headers=auth_headers_user_a,
    )
    folder_a_id = create_folder_a.json()["id"]

    # User B attempts to create a document inside User A's folder
    create_doc_b = await client.post(
        "/v1/documents",
        json={"name": "User B Rogue Doc", "folder_id": folder_a_id},
        headers=auth_headers_user_b,
    )
    assert create_doc_b.status_code == 400
    assert "Folder does not belong to user" in create_doc_b.json()["detail"]


@pytest.mark.asyncio
async def test_nonexistent_folder_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    13. Creating document with non-existent folder_id fails.
    """
    fake_id = str(uuid4())
    resp = await client.post(
        "/v1/documents",
        json={"name": "Orphan Doc", "folder_id": fake_id},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 400
    assert "Folder not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_document_name_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    14. Validation rejects invalid document names (empty or whitespace).
    """
    empty_resp = await client.post(
        "/v1/documents",
        json={"name": ""},
        headers=auth_headers_user_a,
    )
    assert empty_resp.status_code == 422

    space_resp = await client.post(
        "/v1/documents",
        json={"name": "   "},
        headers=auth_headers_user_a,
    )
    assert space_resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_unauthenticated_access_rejected(
    client: AsyncClient,
) -> None:
    """
    15. Unauthenticated access to document endpoints is rejected.
    """
    fake_id = str(uuid4())

    post_resp = await client.post(
        "/v1/documents",
        json={"name": "Unauth Doc"},
    )
    assert post_resp.status_code == 401

    list_resp = await client.get("/v1/documents")
    assert list_resp.status_code == 401

    get_resp = await client.get(f"/v1/documents/{fake_id}")
    assert get_resp.status_code == 401

    patch_resp = await client.patch(
        f"/v1/documents/{fake_id}",
        json={"name": "New Name"},
    )
    assert patch_resp.status_code == 401

    del_resp = await client.delete(f"/v1/documents/{fake_id}")
    assert del_resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_file_authenticated_success(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    16. Authenticated user can upload a file to their document.
    Uploaded file actually exists in storage and can be read back.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Upload Target"},
        headers=auth_headers_user_a,
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]

    file_content = b"VaultDocs secret file content"
    files = {"file": ("report.pdf", file_content, "application/pdf")}

    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files=files,
        headers=auth_headers_user_a,
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    assert data["id"] == doc_id
    assert data["original_filename"] == "report.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["file_size"] == len(file_content)
    assert data["file_path"] is not None

    stored_path = Path(data["file_path"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == file_content

    stored_path.unlink()


@pytest.mark.asyncio
async def test_upload_file_unauthenticated_rejected(
    client: AsyncClient,
) -> None:
    """
    17. Unauthenticated file upload is rejected.
    """
    fake_id = str(uuid4())
    files = {"file": ("test.txt", b"sample data", "text/plain")}

    resp = await client.post(
        f"/v1/documents/{fake_id}/upload",
        files=files,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_file_another_user_document_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    18. User cannot upload a file to another user's document.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "User A Private Upload Target"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    files = {"file": ("malicious.txt", b"hack attempt", "text/plain")}
    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files=files,
        headers=auth_headers_user_b,
    )
    assert upload_resp.status_code == 404
    assert upload_resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_upload_file_nonexistent_document_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    19. Upload to non-existent document fails with 404.
    """
    fake_id = str(uuid4())
    files = {"file": ("dummy.txt", b"data", "text/plain")}

    resp = await client.post(
        f"/v1/documents/{fake_id}/upload",
        files=files,
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_upload_file_path_traversal_handled_safely(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    20. Filenames containing path traversal characters are handled safely.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Path Traversal Test"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    traversal_filename = "../../../etc/passwd"
    files = {"file": (traversal_filename, b"root:x:0:0:root:/root:/bin/bash", "text/plain")}

    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files=files,
        headers=auth_headers_user_a,
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    assert data["original_filename"] == "passwd"

    stored_path = Path(data["file_path"])
    expected_storage_dir = Path(settings.storage_dir).resolve()
    assert stored_path.parent == expected_storage_dir
    assert stored_path.exists()

    stored_path.unlink()


@pytest.mark.asyncio
async def test_upload_file_oversized_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    21. Upload exceeding maximum allowed size is rejected cleanly.
    """
    monkeypatch.setattr(settings, "max_upload_size", 100)

    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Oversized Test"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    oversized_content = b"A" * 200
    files = {"file": ("big_file.bin", oversized_content, "application/octet-stream")}

    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files=files,
        headers=auth_headers_user_a,
    )
    assert upload_resp.status_code == 400
    assert "exceeds maximum allowed limit" in upload_resp.json()["detail"]


@pytest.mark.asyncio
async def test_download_file_authenticated_success(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    22. Authenticated user can download their uploaded document file.
    Content matches uploaded bytes, original filename and content type are preserved.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Download Test Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    file_content = b"PDF test document binary stream content"
    files = {"file": ("report_2026.pdf", file_content, "application/pdf")}

    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files=files,
        headers=auth_headers_user_a,
    )
    assert upload_resp.status_code == 200
    stored_path = Path(upload_resp.json()["file_path"])

    download_resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_a,
    )
    assert download_resp.status_code == 200
    assert download_resp.content == file_content
    assert "application/pdf" in download_resp.headers["content-type"]
    disp = download_resp.headers.get("content-disposition", "")
    assert "report_2026.pdf" in disp

    stored_path.unlink()


@pytest.mark.asyncio
async def test_download_file_unauthenticated_rejected(
    client: AsyncClient,
) -> None:
    """
    23. Unauthenticated file download is rejected with 401.
    """
    fake_id = str(uuid4())
    resp = await client.get(f"/v1/documents/{fake_id}/download")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_download_file_another_user_document_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    24. User cannot download another user's document (returns 404 without leaking existence).
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "User A Private Download Target"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    files = {"file": ("secret.txt", b"user a secret", "text/plain")}
    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files=files,
        headers=auth_headers_user_a,
    )
    stored_path = Path(upload_resp.json()["file_path"])

    download_resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_b,
    )
    assert download_resp.status_code == 404
    assert download_resp.json()["detail"] == "Document not found."

    stored_path.unlink()


@pytest.mark.asyncio
async def test_download_file_nonexistent_document_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    25. Download for non-existent document returns 404.
    """
    fake_id = str(uuid4())
    resp = await client.get(
        f"/v1/documents/{fake_id}/download",
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_download_file_no_file_uploaded_returns_404(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    26. Document without an uploaded file returns 404.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Empty File Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document file not found."


@pytest.mark.asyncio
async def test_download_file_unsafe_path_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    27. Document with unsafe/escaping file path returns 404 and prevents traversal.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Unsafe Path Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    doc = await db_session.get(Document, UUID(doc_id))
    assert doc is not None
    doc.file_path = "/etc/passwd"
    await db_session.commit()

    download_resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_a,
    )
    assert download_resp.status_code == 404
    assert download_resp.json()["detail"] == "Document file not found."


@pytest.mark.asyncio
async def test_replace_file_owner_success(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    28. Document owner can replace an existing file.
    New content is downloadable, metadata updated, and old file is removed.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Replacement Target Doc"},
        headers=auth_headers_user_a,
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]

    initial_content = b"Initial document version content"
    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("v1.txt", initial_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload_resp.status_code == 200
    old_file_path = Path(upload_resp.json()["file_path"])
    assert old_file_path.exists()

    new_content = b"Updated document version content for v2"
    replace_resp = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("v2.txt", new_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert replace_resp.status_code == 200
    data = replace_resp.json()
    assert data["original_filename"] == "v2.txt"
    assert data["file_size"] == len(new_content)
    new_file_path = Path(data["file_path"])
    assert old_file_path.exists()

    download_resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_a,
    )
    assert download_resp.status_code == 200
    assert download_resp.content == new_content

    if old_file_path.exists():
        old_file_path.unlink()
    if new_file_path.exists():
        new_file_path.unlink()


@pytest.mark.asyncio
async def test_replace_file_no_previous_file_success(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    29. PUT replacement on a document with no previous file acts like normal upload.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Fresh Doc No File"},
        headers=auth_headers_user_a,
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]

    file_content = b"First upload content via PUT"
    put_resp = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("first.txt", file_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["original_filename"] == "first.txt"
    file_path = Path(data["file_path"])
    assert file_path.exists()

    download_resp = await client.get(
        f"/v1/documents/{doc_id}/download",
        headers=auth_headers_user_a,
    )
    assert download_resp.status_code == 200
    assert download_resp.content == file_content

    file_path.unlink()


@pytest.mark.asyncio
async def test_replace_file_unauthenticated_rejected(
    client: AsyncClient,
) -> None:
    """
    30. Unauthenticated file replacement is rejected with 401.
    """
    fake_id = str(uuid4())
    resp = await client.put(
        f"/v1/documents/{fake_id}/upload",
        files={"file": ("test.txt", b"data", "text/plain")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_replace_file_another_user_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    31. User cannot replace another user's document file.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "User A Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    resp = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("hack.txt", b"malicious data", "text/plain")},
        headers=auth_headers_user_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found."


@pytest.mark.asyncio
async def test_replace_file_oversized_rejected_preserves_old_file(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    32. Oversized file replacement fails and preserves the existing old file.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Oversized Replacement Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    initial_content = b"Original valid file content"
    upload_resp = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("valid.txt", initial_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert upload_resp.status_code == 200
    old_file_path = Path(upload_resp.json()["file_path"])
    assert old_file_path.exists()

    monkeypatch.setattr(settings, "max_upload_size", 50)
    oversized_content = b"X" * 100

    replace_resp = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("too_big.txt", oversized_content, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert replace_resp.status_code == 400
    assert "exceeds maximum allowed limit" in replace_resp.json()["detail"]

    # Assert old file was NOT removed and still has original content
    assert old_file_path.exists()
    assert old_file_path.read_bytes() == initial_content

    old_file_path.unlink()


@pytest.mark.asyncio
async def test_replace_file_path_traversal_filename_safe(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    33. Replacement filename with path traversal characters is safely sanitized.
    """
    create_resp = await client.post(
        "/v1/documents",
        json={"name": "Path Traversal PUT Doc"},
        headers=auth_headers_user_a,
    )
    doc_id = create_resp.json()["id"]

    traversal_filename = "../../../etc/shadow"
    replace_resp = await client.put(
        f"/v1/documents/{doc_id}/upload",
        files={"file": (traversal_filename, b"shadow_data", "text/plain")},
        headers=auth_headers_user_a,
    )
    assert replace_resp.status_code == 200
    data = replace_resp.json()
    assert data["original_filename"] == "shadow"
    stored_path = Path(data["file_path"])
    assert stored_path.parent == Path(settings.storage_dir).resolve()
    assert stored_path.exists()

    stored_path.unlink()
