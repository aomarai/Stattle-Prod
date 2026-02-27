from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from services.github import GitHubService


class MockResponse:
    def __init__(self, json_data, headers=None):
        self._json_data = json_data
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


@pytest.fixture
def service():
    return GitHubService("test-token")


@pytest.mark.asyncio
async def test_get_client_singleton(monkeypatch):
    GitHubService._client = None
    mock_client = Mock(spec=httpx.AsyncClient)
    mock_factory = Mock(return_value=mock_client)
    monkeypatch.setattr(httpx, "AsyncClient", mock_factory)

    client1 = await GitHubService.get_client()
    client2 = await GitHubService.get_client()

    assert client1 is client2
    mock_factory.assert_called_once()


@pytest.mark.asyncio
async def test_close_client_closes_and_resets():
    mock_client = Mock(spec=httpx.AsyncClient)
    mock_client.aclose = AsyncMock()
    GitHubService._client = mock_client

    await GitHubService.close_client()

    mock_client.aclose.assert_awaited_once()
    assert GitHubService._client is None


@pytest.mark.asyncio
async def test_get_non_paginated_returns_json(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    response = MockResponse({"login": "octocat"})
    mock_client.get = AsyncMock(return_value=response)
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    result = await service.get("user", params={"per_page": 1})

    assert result == {"login": "octocat"}
    mock_client.get.assert_awaited_once_with(
        "https://api.github.com/user", headers=service.headers
    )


@pytest.mark.asyncio
async def test_get_paginated_aggregates_pages(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    response1 = MockResponse(
        [{"id": 1}],
        headers={
            "Link": '<https://api.github.com/users/octo/events?page=2>; rel="next"'
        },
    )
    response2 = MockResponse([{"id": 2}], headers={})
    mock_client.get = AsyncMock(side_effect=[response1, response2])
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    result = await service.get(
        "users/octo/events", params={"per_page": 1}, paginate=True
    )

    assert result == [{"id": 1}, {"id": 2}]
    assert mock_client.get.await_count == 2
    first_call = mock_client.get.await_args_list[0]
    second_call = mock_client.get.await_args_list[1]
    assert first_call.kwargs["params"] == {"per_page": 1}
    assert second_call.kwargs["params"] == {}


@pytest.mark.asyncio
async def test_get_raises_http_status_error(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    request = httpx.Request("GET", "https://api.github.com/user")
    response = httpx.Response(401, request=request)
    mock_client.get = AsyncMock(return_value=response)
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await service.get("user")


@pytest.mark.asyncio
async def test_get_user_info_calls_get(service, monkeypatch):
    service.get = AsyncMock(return_value={"id": 1})

    result = await service.get_user_info()

    assert result == {"id": 1}
    service.get.assert_awaited_once_with("user")


@pytest.mark.asyncio
async def test_get_user_events_calls_get(service, monkeypatch):
    service.get = AsyncMock(return_value=[{"id": 1}])

    result = await service.get_user_events("octo", per_page=50)

    assert result == [{"id": 1}]
    service.get.assert_awaited_once_with("users/octo/events", params={"per_page": 50})
