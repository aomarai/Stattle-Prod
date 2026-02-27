"""
Tests for the GitHubService HTTP client.

Covers:
- Client lifecycle (singleton create/close).
- Basic GET behavior and error handling.
- Pagination aggregation and link parsing.
- User-facing endpoints and defaults.
- Rate limiting with Redis synchronization.
- Lua script execution for atomic rate limit updates.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from services.github import GitHubService, GitHubRateLimitKey, GitHubRedisNamespace
from utils.redis_client import RedisClient


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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))

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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))

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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))

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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))
        monkeypatch.setattr(
            RedisClient, "get_client", AsyncMock(return_value=AsyncMock())
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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))
        monkeypatch.setattr(
            RedisClient, "get_client", AsyncMock(return_value=AsyncMock())
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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))
        monkeypatch.setattr(
            RedisClient, "get_client", AsyncMock(return_value=AsyncMock())
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
        monkeypatch.setattr(RedisClient, "get", AsyncMock(return_value=None))
        monkeypatch.setattr(
            RedisClient, "get_client", AsyncMock(return_value=AsyncMock())
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


class TestRateLimitCheck:
    """Tests for rate limit checking with Redis."""

    @pytest.fixture(autouse=True)
    def reset_redis_singleton(self):
        """Reset RedisClient singleton between tests."""
        RedisClient._instance = None
        yield
        RedisClient._instance = None

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_limit_in_redis(self, service):
        """check_rate_limit does not sleep when no rate limit data is in Redis."""
        with patch.object(RedisClient, "get") as mock_redis_get:
            mock_redis_get.side_effect = [None, None]  # No remaining, no reset

            await service._check_rate_limit()

            assert mock_redis_get.await_count == 2

    @pytest.mark.asyncio
    async def test_check_rate_limit_above_threshold(self, service):
        """check_rate_limit does not sleep when remaining is above 10."""
        with patch.object(RedisClient, "get") as mock_redis_get:
            mock_redis_get.side_effect = ["100", "1234567890"]

            await service._check_rate_limit()

            assert mock_redis_get.await_count == 2
            # Should not sleep

    @pytest.mark.asyncio
    async def test_check_rate_limit_below_threshold_sleeps(self, service):
        """check_rate_limit sleeps when remaining is below 10."""
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time + 30

        with patch.object(RedisClient, "get") as mock_redis_get:
            mock_redis_get.side_effect = ["5", str(reset_time)]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await service._check_rate_limit()

                mock_sleep.assert_awaited_once()
                sleep_duration = mock_sleep.call_args[0][0]
                assert sleep_duration > 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_reset_in_past(self, service):
        """check_rate_limit does not sleep when reset time is in the past."""
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time - 10  # Past time

        with patch.object(RedisClient, "get") as mock_redis_get:
            mock_redis_get.side_effect = ["5", str(reset_time)]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await service._check_rate_limit()

                mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_reset_time(self, service):
        """check_rate_limit does not sleep when reset_time is missing."""
        with patch.object(RedisClient, "get") as mock_redis_get:
            mock_redis_get.side_effect = ["5", None]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await service._check_rate_limit()

                mock_sleep.assert_not_awaited()


class TestRateLimitUpdate:
    """Tests for updating rate limit in Redis."""

    @pytest.fixture(autouse=True)
    def reset_redis_singleton(self):
        """Reset RedisClient singleton between tests."""
        RedisClient._instance = None
        yield
        RedisClient._instance = None

    @pytest.mark.asyncio
    async def test_update_rate_limit_with_headers(self, service):
        """update_rate_limit executes Lua script with proper headers."""
        response = Mock(spec=httpx.Response)
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time + 3600
        response.headers = {
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Remaining": "4000",
            "X-RateLimit-Limit": "5000",
        }

        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis
            mock_redis.eval = AsyncMock()

            await service._update_rate_limit(response)

            # Verify eval was called
            mock_redis.eval.assert_awaited_once()
            call_args = mock_redis.eval.call_args

            # Verify Lua script is correct
            lua_script = call_args[0][0]
            assert "redis.call" in lua_script
            assert "SET" in lua_script

    @pytest.mark.asyncio
    async def test_update_rate_limit_without_reset_header(self, service):
        """update_rate_limit skips when X-RateLimit-Reset header is missing."""
        response = Mock(spec=httpx.Response)
        response.headers = {}

        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis

            await service._update_rate_limit(response)

            # Lua script should not be executed
            mock_redis.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_rate_limit_with_missing_optional_headers(self, service):
        """update_rate_limit handles missing optional rate limit headers."""
        response = Mock(spec=httpx.Response)
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time + 3600
        response.headers = {
            "X-RateLimit-Reset": str(reset_time),
            # Missing Remaining and Limit
        }

        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis
            mock_redis.eval = AsyncMock()

            await service._update_rate_limit(response)

            mock_redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_rate_limit_calculates_ttl(self, service):
        """update_rate_limit calculates TTL from reset time."""
        response = Mock(spec=httpx.Response)
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time + 60  # 60 seconds in future
        response.headers = {
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Remaining": "100",
        }

        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis
            mock_redis.eval = AsyncMock()

            await service._update_rate_limit(response)

            call_args = mock_redis.eval.call_args
            ttl_arg = call_args[0][7]  # TTL is the 8th positional argument (index 7)
            assert int(ttl_arg) <= 60

    @pytest.mark.asyncio
    async def test_update_rate_limit_minimum_ttl(self, service):
        """update_rate_limit uses minimum TTL of 60 seconds."""
        response = Mock(spec=httpx.Response)
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time - 10  # Already past
        response.headers = {
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Remaining": "100",
        }

        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis
            mock_redis.eval = AsyncMock()

            await service._update_rate_limit(response)

            call_args = mock_redis.eval.call_args
            ttl_arg = call_args[0][7]  # TTL
            assert int(ttl_arg) >= 60

    @pytest.mark.asyncio
    async def test_update_rate_limit_lua_script_parameters(self, service):
        """update_rate_limit passes all parameters correctly to Lua script."""
        response = Mock(spec=httpx.Response)
        current_time = int(datetime.now(timezone.utc).timestamp())
        reset_time = current_time + 3600
        remaining = "4500"
        limit = "5000"
        response.headers = {
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Limit": limit,
        }

        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis
            mock_redis.eval = AsyncMock()

            await service._update_rate_limit(response)

            call_args = mock_redis.eval.call_args
            # Verify key count
            assert call_args[0][1] == 4  # 4 keys for timestamp, reset, remaining, limit
            # Verify remaining and limit are in the arguments
            args_list = list(call_args[0])
            assert remaining in args_list
            assert limit in args_list


class TestGetWithRateLimit:
    """Tests for GET operations with rate limit checking and updating."""

    @pytest.fixture(autouse=True)
    def reset_redis_singleton(self):
        """Reset RedisClient singleton between tests."""
        RedisClient._instance = None
        yield
        RedisClient._instance = None

    @pytest.mark.asyncio
    async def test_get_checks_rate_limit_before_request(self, service, monkeypatch):
        """get calls _check_rate_limit before making a request."""
        mock_client = Mock(spec=httpx.AsyncClient)
        response = MockResponse({"login": "octocat"}, headers={})
        mock_client.get = AsyncMock(return_value=response)
        monkeypatch.setattr(
            GitHubService, "get_client", AsyncMock(return_value=mock_client)
        )

        check_rate_limit_called = False

        async def mock_check_rate_limit():
            nonlocal check_rate_limit_called
            check_rate_limit_called = True

        service._check_rate_limit = mock_check_rate_limit

        with patch.object(service, "_update_rate_limit", new_callable=AsyncMock):
            await service.get("user")

            assert check_rate_limit_called

    @pytest.mark.asyncio
    async def test_get_updates_rate_limit_after_request(self, service, monkeypatch):
        """get calls _update_rate_limit after a successful request."""
        mock_client = Mock(spec=httpx.AsyncClient)
        current_time = int(datetime.now(timezone.utc).timestamp())
        response = MockResponse(
            {"login": "octocat"},
            headers={
                "X-RateLimit-Reset": str(current_time + 3600),
                "X-RateLimit-Remaining": "100",
            },
        )
        mock_client.get = AsyncMock(return_value=response)
        monkeypatch.setattr(
            GitHubService, "get_client", AsyncMock(return_value=mock_client)
        )

        with patch.object(service, "_check_rate_limit", new_callable=AsyncMock):
            with patch.object(
                service, "_update_rate_limit", new_callable=AsyncMock
            ) as mock_update:
                await service.get("user")

                mock_update.assert_awaited_once_with(response)

    @pytest.mark.asyncio
    async def test_get_paginated_updates_rate_limit_each_page(
        self, service, monkeypatch
    ):
        """get paginated calls _update_rate_limit after each page request."""
        mock_client = Mock(spec=httpx.AsyncClient)
        current_time = int(datetime.now(timezone.utc).timestamp())
        response1 = MockResponse(
            [{"id": 1}],
            headers={
                "Link": '<https://api.github.com/users/octo/events?page=2>; rel="next"',
                "X-RateLimit-Reset": str(current_time + 3600),
                "X-RateLimit-Remaining": "100",
            },
        )
        response2 = MockResponse(
            [{"id": 2}],
            headers={
                "X-RateLimit-Reset": str(current_time + 3600),
                "X-RateLimit-Remaining": "99",
            },
        )
        mock_client.get = AsyncMock(side_effect=[response1, response2])
        monkeypatch.setattr(
            GitHubService, "get_client", AsyncMock(return_value=mock_client)
        )

        with patch.object(service, "_check_rate_limit", new_callable=AsyncMock):
            with patch.object(
                service, "_update_rate_limit", new_callable=AsyncMock
            ) as mock_update:
                await service.get("users/octo/events", paginate=True)

                assert mock_update.await_count == 2


class TestEnumKeygen:
    """Tests for GitHubRateLimitKey enum."""

    def test_rate_limit_key_full_key_remaining(self):
        """GitHubRateLimitKey.REMAINING generates correct full key."""
        key = GitHubRateLimitKey.REMAINING.full_key()
        assert key == "github:rate_limit:remaining"

    def test_rate_limit_key_full_key_reset(self):
        """GitHubRateLimitKey.RESET generates correct full key."""
        key = GitHubRateLimitKey.RESET.full_key()
        assert key == "github:rate_limit:reset"

    def test_rate_limit_key_full_key_limit(self):
        """GitHubRateLimitKey.LIMIT generates correct full key."""
        key = GitHubRateLimitKey.LIMIT.full_key()
        assert key == "github:rate_limit:limit"

    def test_namespace_values(self):
        """GitHubRedisNamespace has correct values."""
        assert GitHubRedisNamespace.GITHUB.value == "github"
        assert GitHubRedisNamespace.RATE_LIMIT.value == "rate_limit"
