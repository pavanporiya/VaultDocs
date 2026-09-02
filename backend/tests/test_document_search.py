"""
Integration tests for Document Search endpoint (GET /v1/documents/search).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_unauthenticated(client: AsyncClient) -> None:
    """
    Unauthenticated request to search endpoint should be rejected with 401.
    """
    response = await client.get("/v1/documents/search")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_exact_name(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Search document by exact name match.
    """
    await client.post(
        "/v1/documents",
        json={"name": "Financial Report 2026"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "Project Specifications"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        params={"q": "Financial Report 2026"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "Financial Report 2026"


@pytest.mark.asyncio
async def test_search_partial_name(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Search document by partial name substring match.
    """
    await client.post(
        "/v1/documents",
        json={"name": "Annual Financial Report"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "Quarterly Financial Summary"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "Design Mockup"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        params={"q": "Financial"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    names = {doc["name"] for doc in results}
    assert names == {"Annual Financial Report", "Quarterly Financial Summary"}


@pytest.mark.asyncio
async def test_search_case_insensitive(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Search is case-insensitive.
    """
    await client.post(
        "/v1/documents",
        json={"name": "CONFIDENTIAL STRATEGY"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        params={"q": "confidential strategy"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "CONFIDENTIAL STRATEGY"


@pytest.mark.asyncio
async def test_search_empty_query(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Empty or missing query returns user's documents normally.
    """
    await client.post(
        "/v1/documents",
        json={"name": "Doc Alpha"},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "Doc Beta"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2

    response_empty_str = await client.get(
        "/v1/documents/search",
        params={"q": "   "},
        headers=auth_headers_user_a,
    )
    assert response_empty_str.status_code == 200
    assert len(response_empty_str.json()) == 2


@pytest.mark.asyncio
async def test_search_folder_id_filtering(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    folder_id parameter filters search results to that specific folder.
    """
    folder_resp = await client.post(
        "/v1/folders",
        json={"name": "Target Folder"},
        headers=auth_headers_user_a,
    )
    assert folder_resp.status_code == 201
    folder_id = folder_resp.json()["id"]

    await client.post(
        "/v1/documents",
        json={"name": "Folder Report", "folder_id": folder_id},
        headers=auth_headers_user_a,
    )
    await client.post(
        "/v1/documents",
        json={"name": "Root Report"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        params={"q": "Report", "folder_id": folder_id},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "Folder Report"
    assert results[0]["folder_id"] == folder_id


@pytest.mark.asyncio
async def test_search_user_isolation(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """
    Users can never see another user's documents in search results.
    """
    await client.post(
        "/v1/documents",
        json={"name": "Top Secret Document"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        params={"q": "Secret"},
        headers=auth_headers_user_b,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_no_match_result(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    Query with no matching documents returns an empty list.
    """
    await client.post(
        "/v1/documents",
        json={"name": "Existing Document"},
        headers=auth_headers_user_a,
    )

    response = await client.get(
        "/v1/documents/search",
        params={"q": "NonExistentTerm"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    results = response.json()
    assert results == []


@pytest.mark.asyncio
async def test_search_limit_and_offset(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """
    limit and offset parameters paginate search results.
    """
    for i in range(5):
        await client.post(
            "/v1/documents",
            json={"name": f"Item {i:02d}"},
            headers=auth_headers_user_a,
        )

    # Search with limit=2, offset=0
    resp_p1 = await client.get(
        "/v1/documents/search",
        params={"limit": 2, "offset": 0},
        headers=auth_headers_user_a,
    )
    assert resp_p1.status_code == 200
    p1_results = resp_p1.json()
    assert len(p1_results) == 2

    # Search with limit=2, offset=2
    resp_p2 = await client.get(
        "/v1/documents/search",
        params={"limit": 2, "offset": 2},
        headers=auth_headers_user_a,
    )
    assert resp_p2.status_code == 200
    p2_results = resp_p2.json()
    assert len(p2_results) == 2

    # Ensure pages contain different documents
    p1_ids = {doc["id"] for doc in p1_results}
    p2_ids = {doc["id"] for doc in p2_results}
    assert p1_ids.isdisjoint(p2_ids)
