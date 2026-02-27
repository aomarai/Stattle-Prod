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
        "https://api.github.com/user",
        headers=service.headers,
        params={"per_page": 1},
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
    service.get.assert_awaited_once_with(
        "users/octo/events", params={"per_page": 50}, paginate=True
    )


@pytest.mark.asyncio
async def test_get_user_events_default_per_page(service, monkeypatch):
    service.get = AsyncMock(return_value=[{"id": 1}])

    result = await service.get_user_events("octo")

    assert result == [{"id": 1}]
    service.get.assert_awaited_once_with(
        "users/octo/events", params={"per_page": 100}, paginate=True
    )


def test_extract_next_url_valid_link(service):
    link_header = '<https://api.github.com/page2>; rel="next"'
    result = service._extract_next_url(link_header)
    assert result == "https://api.github.com/page2"


def test_extract_next_url_no_next_rel(service):
    link_header = '<https://api.github.com/page1>; rel="prev"'
    result = service._extract_next_url(link_header)
    assert result is None


def test_extract_next_url_none_header(service):
    result = service._extract_next_url(None)
    assert result is None


def test_extract_next_url_empty_string(service):
    result = service._extract_next_url("")
    assert result is None


def test_extract_next_url_malformed_no_closing_bracket(service):
    link_header = '<https://api.github.com/page2; rel="next"'
    result = service._extract_next_url(link_header)
    assert result is None


def test_extract_next_url_multiple_links(service):
    link_header = '<https://api.github.com/page1>; rel="prev", <https://api.github.com/page3>; rel="next"'
    result = service._extract_next_url(link_header)
    assert result == "https://api.github.com/page3"


def test_extract_next_url_with_query_params(service):
    link_header = '<https://api.github.com/page2?per_page=100&page=2>; rel="next"'
    result = service._extract_next_url(link_header)
    assert result == "https://api.github.com/page2?per_page=100&page=2"


@pytest.mark.asyncio
async def test_get_paginated_single_page(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    response = MockResponse([{"id": 1}], headers={})
    mock_client.get = AsyncMock(return_value=response)
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    result = await service.get("users/octo/events", paginate=True)

    assert result == [{"id": 1}]
    mock_client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_paginated_three_pages(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    response1 = MockResponse(
        [{"id": 1}],
        headers={
            "Link": '<https://api.github.com/users/octo/events?page=2>; rel="next"'
        },
    )
    response2 = MockResponse(
        [{"id": 2}],
        headers={
            "Link": '<https://api.github.com/users/octo/events?page=3>; rel="next"'
        },
    )
    response3 = MockResponse([{"id": 3}], headers={})
    mock_client.get = AsyncMock(side_effect=[response1, response2, response3])
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    result = await service.get(
        "users/octo/events", params={"per_page": 1}, paginate=True
    )

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert mock_client.get.await_count == 3


@pytest.mark.asyncio
async def test_get_paginated_empty_response(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    response = MockResponse([], headers={})
    mock_client.get = AsyncMock(return_value=response)
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    result = await service.get("users/octo/events", paginate=True)

    assert result == []


@pytest.mark.asyncio
async def test_get_non_paginated_with_params(service, monkeypatch):
    mock_client = Mock(spec=httpx.AsyncClient)
    response = MockResponse({"login": "octocat", "id": 123})
    mock_client.get = AsyncMock(return_value=response)
    monkeypatch.setattr(
        GitHubService, "get_client", AsyncMock(return_value=mock_client)
    )

    result = await service.get("user", params={"foo": "bar"})

    assert result == {"login": "octocat", "id": 123}
    mock_client.get.assert_awaited_once_with(
        "https://api.github.com/user",
        headers=service.headers,
        params={"foo": "bar"},
    )


@pytest.mark.asyncio
async def test_close_client_when_none():
    GitHubService._client = None
    await GitHubService.close_client()
    assert GitHubService._client is None


def test_service_initialization():
    service = GitHubService("my-token-123")
    assert service.base_url == "https://api.github.com"
    assert service.headers["Authorization"] == "token my-token-123"
    assert service.headers["Accept"] == "application/vnd.github.v3+json"
