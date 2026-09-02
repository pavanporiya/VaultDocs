"""
Unit and integration tests for Folder Management Module.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from vaultdocs.models.user import User


@pytest.mark.asyncio
async def test_create_root_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a: User,
) -> None:
    """
    1. Authenticated user can create a root folder.
    """
    response = await client.post(
        "/v1/folders",
        json={"name": "Documents Root"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Documents Root"
    assert data["parent_id"] is None
    assert data["owner_id"] == str(user_a.id)
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_child_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    user_a: User,
) -> None:
    """
    2. Authenticated user can create a child folder.
    """
    root_resp = await client.post(
        "/v1/folders",
        json={"name": "Root Project"},
        headers=auth_headers_user_a,
    )
    assert root_resp.status_code == 201
    root_id = root_resp.json()["id"]

    child_resp = await client.post(
        "/v1/folders",
        json={"name": "Child Specs", "parent_id": root_id},
        headers=auth_headers_user_a,
    )
    assert child_resp.status_code == 201
    child_data = child_resp.json()
    assert child_data["name"] == "Child Specs"
    assert child_data["parent_id"] == root_id
    assert child_data["owner_id"] == str(user_a.id)


@pytest.mark.asyncio
async def test_list_user_folders(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    3. User can list their folders (and only their folders).
    """
    await client.post(
        "/v1/folders",
        json={"name": "User A Folder 1"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/folders",
        json={"name": "User A Folder 2"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/folders",
        json={"name": "User B Folder 1"},
        headers=auth_headers_user_b,
    )

    list_resp = await client.get(
        "/v1/folders",
        headers=auth_headers_user_a,
    )
    assert list_resp.status_code == 200
    folders_a = list_resp.json()
    assert len(folders_a) == 2
    names_a = [f["name"] for f in folders_a]
    assert "User A Folder 1" in names_a
    assert "User A Folder 2" in names_a
    assert "User B Folder 1" not in names_a


@pytest.mark.asyncio
async def test_retrieve_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    4. User can retrieve their folder by ID.
    """
    create_resp = await client.post(
        "/v1/folders",
        json={"name": "Target Folder"},
        headers=auth_headers_user_a,
    )
    folder_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/v1/folders/{folder_id}",
        headers=auth_headers_user_a,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == folder_id
    assert data["name"] == "Target Folder"


@pytest.mark.asyncio
async def test_update_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    5. User can update their folder.
    """
    create_resp = await client.post(
        "/v1/folders",
        json={"name": "Original Name"},
        headers=auth_headers_user_a,
    )
    folder_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/folders/{folder_id}",
        json={"name": "Renamed Folder"},
        headers=auth_headers_user_a,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Renamed Folder"


@pytest.mark.asyncio
async def test_delete_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    6. User can delete their folder.
    """
    create_resp = await client.post(
        "/v1/folders",
        json={"name": "Folder To Delete"},
        headers=auth_headers_user_a,
    )
    folder_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/v1/folders/{folder_id}",
        headers=auth_headers_user_a,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/v1/folders/{folder_id}",
        headers=auth_headers_user_a,
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_another_user_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    7. User cannot access another user's folder.
    """
    create_resp = await client.post(
        "/v1/folders",
        json={"name": "User A Private"},
        headers=auth_headers_user_a,
    )
    folder_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/v1/folders/{folder_id}",
        headers=auth_headers_user_b,
    )
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Folder not found."


@pytest.mark.asyncio
async def test_user_cannot_update_another_user_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    8. User cannot update another user's folder.
    """
    create_resp = await client.post(
        "/v1/folders",
        json={"name": "User A Protected"},
        headers=auth_headers_user_a,
    )
    folder_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/v1/folders/{folder_id}",
        json={"name": "Hacked Name"},
        headers=auth_headers_user_b,
    )
    assert patch_resp.status_code == 404
    assert patch_resp.json()["detail"] == "Folder not found."


@pytest.mark.asyncio
async def test_user_cannot_delete_another_user_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    9. User cannot delete another user's folder.
    """
    create_resp = await client.post(
        "/v1/folders",
        json={"name": "User A Permanent"},
        headers=auth_headers_user_a,
    )
    folder_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/v1/folders/{folder_id}",
        headers=auth_headers_user_b,
    )
    assert del_resp.status_code == 404
    assert del_resp.json()["detail"] == "Folder not found."


@pytest.mark.asyncio
async def test_child_cannot_use_parent_owned_by_another_user(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    10. Child folder cannot use a parent owned by another user.
    """
    create_a = await client.post(
        "/v1/folders",
        json={"name": "User A Parent"},
        headers=auth_headers_user_a,
    )
    parent_id = create_a.json()["id"]

    # User B attempts to create a child under User A's folder
    create_b = await client.post(
        "/v1/folders",
        json={"name": "User B Rogue Child", "parent_id": parent_id},
        headers=auth_headers_user_b,
    )
    assert create_b.status_code == 400
    assert "Parent folder does not belong to user" in create_b.json()["detail"]


@pytest.mark.asyncio
async def test_self_parenting_rejected(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    11. Self-parenting and cycle parenting are rejected.
    """
    folder1_resp = await client.post(
        "/v1/folders",
        json={"name": "Folder 1"},
        headers=auth_headers_user_a,
    )
    f1_id = folder1_resp.json()["id"]

    # Direct self parenting
    self_resp = await client.patch(
        f"/v1/folders/{f1_id}",
        json={"parent_id": f1_id},
        headers=auth_headers_user_a,
    )
    assert self_resp.status_code == 400
    assert "Folder cannot be its own parent" in self_resp.json()["detail"]

    # Cycle parenting: F1 -> F2. Attempt to make F1 parented by F2.
    folder2_resp = await client.post(
        "/v1/folders",
        json={"name": "Folder 2", "parent_id": f1_id},
        headers=auth_headers_user_a,
    )
    f2_id = folder2_resp.json()["id"]

    cycle_resp = await client.patch(
        f"/v1/folders/{f1_id}",
        json={"parent_id": f2_id},
        headers=auth_headers_user_a,
    )
    assert cycle_resp.status_code == 400
    assert "Cannot set a descendant folder as parent" in cycle_resp.json()["detail"]


@pytest.mark.asyncio
async def test_validation_rejects_invalid_folder_name(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    12. Validation rejects invalid folder names (empty or whitespace).
    """
    empty_resp = await client.post(
        "/v1/folders",
        json={"name": ""},
        headers=auth_headers_user_a,
    )
    assert empty_resp.status_code == 422

    space_resp = await client.post(
        "/v1/folders",
        json={"name": "   "},
        headers=auth_headers_user_a,
    )
    assert space_resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_nonexistent_parent_folder(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Bonus: Creating folder with non-existent parent_id fails.
    """
    fake_id = str(uuid4())
    resp = await client.post(
        "/v1/folders",
        json={"name": "Orphan Folder", "parent_id": fake_id},
        headers=auth_headers_user_a,
    )
    assert resp.status_code == 400
    assert "Parent folder not found" in resp.json()["detail"]
