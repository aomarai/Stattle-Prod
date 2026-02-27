"""
Tests for the GitHubService HTTP client.

Covers:
- Client lifecycle (singleton create/close).
- Basic GET behavior and error handling.
- Pagination aggregation and link parsing.
- User-facing endpoints and defaults.
"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from services.github import GitHubService


class MockResponse:
    """Simple response stub for async client tests."""

    def __init__(self, json_data, headers=None):
        self._json_data = json_data
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


@pytest.fixture
def service():
    """Provide a GitHubService instance with a test token."""
    return GitHubService("test-token")


class TestClientLifecycle:
    """Tests for singleton client creation and teardown."""

    @pytest.mark.asyncio
    async def test_get_client_singleton(self, monkeypatch):
        """get_client returns the same singleton instance on repeat calls."""
        GitHubService._client = None
        mock_client = Mock(spec=httpx.AsyncClient)
        mock_factory = Mock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_factory)

        client1 = await GitHubService.get_client()
        client2 = await GitHubService.get_client()

        assert client1 is client2
        mock_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_client_closes_and_resets(self):
        """close_client closes the client and clears the singleton."""
        mock_client = Mock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock()
        GitHubService._client = mock_client

        await GitHubService.close_client()

        mock_client.aclose.assert_awaited_once()
        assert GitHubService._client is None

    @pytest.mark.asyncio
    async def test_close_client_when_none(self):
        """close_client is a no-op when no client exists."""
        GitHubService._client = None
        await GitHubService.close_client()
        assert GitHubService._client is None


class TestGetRequests:
    """Tests for non-paginated GET requests and errors."""

    @pytest.mark.asyncio
    async def test_get_non_paginated_returns_json(self, service, monkeypatch):
        """Non-paginated GET returns JSON body."""
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
    async def test_get_non_paginated_with_params(self, service, monkeypatch):
        """Non-paginated GET forwards query params."""
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
    async def test_get_raises_http_status_error(self, service, monkeypatch):
        """Non-2xx responses raise HTTPStatusError."""
        mock_client = Mock(spec=httpx.AsyncClient)
        request = httpx.Request("GET", "https://api.github.com/user")
        response = httpx.Response(401, request=request)
        mock_client.get = AsyncMock(return_value=response)
        monkeypatch.setattr(
            GitHubService, "get_client", AsyncMock(return_value=mock_client)
        )

        with pytest.raises(httpx.HTTPStatusError):
            await service.get("user")


class TestPagination:
    """Tests for pagination aggregation behavior."""

    @pytest.mark.asyncio
    async def test_get_paginated_aggregates_pages(self, service, monkeypatch):
        """Paginated GET aggregates results and clears params after first page."""
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
    async def test_get_paginated_single_page(self, service, monkeypatch):
        """Paginated GET returns single page when Link header is missing."""
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
    async def test_get_paginated_three_pages(self, service, monkeypatch):
        """Paginated GET aggregates results across multiple pages."""
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
    async def test_get_paginated_empty_response(self, service, monkeypatch):
        """Paginated GET returns an empty list when there is no data."""
        mock_client = Mock(spec=httpx.AsyncClient)
        response = MockResponse([], headers={})
        mock_client.get = AsyncMock(return_value=response)
        monkeypatch.setattr(
            GitHubService, "get_client", AsyncMock(return_value=mock_client)
        )

        result = await service.get("users/octo/events", paginate=True)

        assert result == []


class TestUserEndpoints:
    """Tests for user-related GitHub endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_info_calls_get(self, service, monkeypatch):
        """get_user_info proxies to the generic get method."""
        service.get = AsyncMock(return_value={"id": 1})

        result = await service.get_user_info()

        assert result == {"id": 1}
        service.get.assert_awaited_once_with("user")

    @pytest.mark.asyncio
    async def test_get_user_events_calls_get(self, service, monkeypatch):
        """get_user_events forwards username and per_page settings."""
        service.get = AsyncMock(return_value=[{"id": 1}])

        result = await service.get_user_events("octo", per_page=50)

        assert result == [{"id": 1}]
        service.get.assert_awaited_once_with(
            "users/octo/events", params={"per_page": 50}, paginate=True
        )

    @pytest.mark.asyncio
    async def test_get_user_events_default_per_page(self, service, monkeypatch):
        """get_user_events uses the default per_page size when omitted."""
        service.get = AsyncMock(return_value=[{"id": 1}])

        result = await service.get_user_events("octo")

        assert result == [{"id": 1}]
        service.get.assert_awaited_once_with(
            "users/octo/events", params={"per_page": 100}, paginate=True
        )


class TestLinkParsing:
    """Tests for GitHub Link header parsing."""

    def test_extract_next_url_valid_link(self, service):
        """Extracts next URL when a valid Link header is present."""
        link_header = '<https://api.github.com/page2>; rel="next"'
        result = service._extract_next_url(link_header)
        assert result == "https://api.github.com/page2"

    def test_extract_next_url_no_next_rel(self, service):
        """Returns None when no next relation exists."""
        link_header = '<https://api.github.com/page1>; rel="prev"'
        result = service._extract_next_url(link_header)
        assert result is None

    def test_extract_next_url_none_header(self, service):
        """Returns None when the Link header is missing."""
        result = service._extract_next_url(None)
        assert result is None

    def test_extract_next_url_empty_string(self, service):
        """Returns None when the Link header is empty."""
        result = service._extract_next_url("")
        assert result is None

    def test_extract_next_url_malformed_no_closing_bracket(self, service):
        """Returns None for malformed Link headers."""
        link_header = '<https://api.github.com/page2; rel="next"'
        result = service._extract_next_url(link_header)
        assert result is None

    def test_extract_next_url_multiple_links(self, service):
        """Selects the next relation when multiple links are present."""
        link_header = '<https://api.github.com/page1>; rel="prev", <https://api.github.com/page3>; rel="next"'
        result = service._extract_next_url(link_header)
        assert result == "https://api.github.com/page3"

    def test_extract_next_url_with_query_params(self, service):
        """Preserves query parameters when extracting next URL."""
        link_header = '<https://api.github.com/page2?per_page=100&page=2>; rel="next"'
        result = service._extract_next_url(link_header)
        assert result == "https://api.github.com/page2?per_page=100&page=2"


class TestServiceInitialization:
    """Tests for GitHubService constructor behavior."""

    def test_service_initialization(self):
        """Constructor sets base URL and auth headers."""
        service = GitHubService("my-token-123")
        assert service.base_url == "https://api.github.com"
        assert service.headers["Authorization"] == "Bearer my-token-123"
        assert service.headers["Accept"] == "application/vnd.github.v3+json"
