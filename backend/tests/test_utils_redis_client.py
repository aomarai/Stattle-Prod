"""
Tests for the RedisClient utility class.

Covers:
- Client lifecycle (singleton creation/closing).
- Get/Set operations with various data types.
- TTL (expiration) handling.
- Error handling and connection failures.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis

from utils.redis_client import RedisClient


@pytest.fixture(autouse=True)
def reset_redis_singleton():
    """Reset the RedisClient singleton before and after each test."""
    RedisClient._instance = None
    yield
    RedisClient._instance = None


class TestRedisClientSingleton:
    """Tests for RedisClient singleton behavior."""

    @pytest.mark.asyncio
    async def test_get_client_creates_instance(self):
        """get_client creates a new Redis instance when none exists."""
        with patch(
            "utils.redis_client.redis.from_url", new_callable=AsyncMock
        ) as mock_from_url:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_from_url.return_value = mock_redis

            client = await RedisClient.get_client()

            assert client is mock_redis
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_singleton_behavior(self):
        """get_client returns the same instance on subsequent calls."""
        with patch(
            "utils.redis_client.redis.from_url", new_callable=AsyncMock
        ) as mock_from_url:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_from_url.return_value = mock_redis

            client1 = await RedisClient.get_client()
            client2 = await RedisClient.get_client()

            assert client1 is client2
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_thread_safe(self):
        """get_client is thread-safe under concurrent access."""
        with patch(
            "utils.redis_client.redis.from_url", new_callable=AsyncMock
        ) as mock_from_url:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_from_url.return_value = mock_redis

            clients = await asyncio.gather(
                RedisClient.get_client(),
                RedisClient.get_client(),
                RedisClient.get_client(),
            )

            assert all(c is clients[0] for c in clients)
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_uses_env_variables(self):
        """get_client respects REDIS_HOST and REDIS_PORT environment variables."""
        with patch.dict(
            "os.environ", {"REDIS_HOST": "redis.example.com", "REDIS_PORT": "6380"}
        ):
            with patch(
                "utils.redis_client.redis.from_url", new_callable=AsyncMock
            ) as mock_from_url:
                mock_redis = AsyncMock(spec=redis.Redis)
                mock_from_url.return_value = mock_redis
                RedisClient._instance = None

                await RedisClient.get_client()

                expected_url = "redis://redis.example.com:6380"
                mock_from_url.assert_called_once()
                call_args = mock_from_url.call_args
                assert expected_url in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_client_default_host_and_port(self):
        """get_client uses default localhost:6379 when env vars are not set."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "utils.redis_client.redis.from_url", new_callable=AsyncMock
            ) as mock_from_url:
                mock_redis = AsyncMock(spec=redis.Redis)
                mock_from_url.return_value = mock_redis
                RedisClient._instance = None

                await RedisClient.get_client()

                expected_url = "redis://localhost:6379"
                mock_from_url.assert_called_once()
                call_args = mock_from_url.call_args
                assert expected_url in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_client_configures_connection_options(self):
        """get_client configures encoding, timeout, and keepalive."""
        with patch(
            "utils.redis_client.redis.from_url", new_callable=AsyncMock
        ) as mock_from_url:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_from_url.return_value = mock_redis

            await RedisClient.get_client()

            call_kwargs = mock_from_url.call_args[1]
            assert call_kwargs["encoding"] == "utf-8"
            assert call_kwargs["decode_responses"] is True
            assert call_kwargs["socket_connect_timeout"] == 5
            assert call_kwargs["socket_keepalive"] is True

    @pytest.mark.asyncio
    async def test_close_closes_instance(self):
        """close closes the Redis instance."""
        mock_redis = AsyncMock(spec=redis.Redis)
        RedisClient._instance = mock_redis

        await RedisClient.close()

        mock_redis.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_when_instance_is_none(self):
        """close is a no-op when no instance exists."""
        RedisClient._instance = None
        await RedisClient.close()
        assert RedisClient._instance is None


class TestRedisClientGet:
    """Tests for RedisClient.get method."""

    @pytest.mark.asyncio
    async def test_get_returns_string_value(self):
        """get returns a string value from Redis."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.get = AsyncMock(return_value="test-value")

            result = await RedisClient.get("test-key")

            assert result == "test-value"
            mock_redis.get.assert_awaited_once_with("test-key")

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self):
        """get returns None when the key does not exist."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.get = AsyncMock(return_value=None)

            result = await RedisClient.get("nonexistent-key")

            assert result is None
            mock_redis.get.assert_awaited_once_with("nonexistent-key")

    @pytest.mark.asyncio
    async def test_get_returns_numeric_string(self):
        """get returns numeric values as strings (due to decode_responses=True)."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.get = AsyncMock(return_value="12345")

            result = await RedisClient.get("numeric-key")

            assert result == "12345"
            assert isinstance(result, str)


class TestRedisClientSet:
    """Tests for RedisClient.set method."""

    @pytest.mark.asyncio
    async def test_set_with_string_value(self):
        """set stores a string value."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("test-key", "test-value")

            mock_redis.set.assert_awaited_once_with("test-key", "test-value", None)

    @pytest.mark.asyncio
    async def test_set_with_integer_value(self):
        """set converts and stores integer values."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("count-key", 42)

            mock_redis.set.assert_awaited_once_with("count-key", 42, None)

    @pytest.mark.asyncio
    async def test_set_with_float_value(self):
        """set converts and stores float values."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("float-key", 3.14159)

            mock_redis.set.assert_awaited_once_with("float-key", 3.14159, None)

    @pytest.mark.asyncio
    async def test_set_with_bytes_value(self):
        """set stores bytes values."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("bytes-key", b"binary-data")

            mock_redis.set.assert_awaited_once_with("bytes-key", b"binary-data", None)

    @pytest.mark.asyncio
    async def test_set_with_expiration_time(self):
        """set stores a value with TTL (expiration time)."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("temp-key", "temp-value", ex=3600)

            mock_redis.set.assert_awaited_once_with("temp-key", "temp-value", 3600)

    @pytest.mark.asyncio
    async def test_set_with_zero_expiration(self):
        """set accepts ex=0 (no expiration)."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("persistent-key", "value", ex=0)

            mock_redis.set.assert_awaited_once_with("persistent-key", "value", 0)

    @pytest.mark.asyncio
    async def test_set_without_expiration(self):
        """set stores a value without TTL when ex is None."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("persistent-key", "value")

            mock_redis.set.assert_awaited_once_with("persistent-key", "value", None)

    @pytest.mark.asyncio
    async def test_set_with_empty_string(self):
        """set handles empty string values."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis
            mock_redis.set = AsyncMock()

            await RedisClient.set("empty-key", "")

            mock_redis.set.assert_awaited_once_with("empty-key", "", None)


class TestRedisClientIntegration:
    """Integration tests for RedisClient operations."""

    @pytest.mark.asyncio
    async def test_set_then_get(self):
        """Set and Get operations work together."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis

            # Simulate set operation
            mock_redis.set = AsyncMock()
            await RedisClient.set("key", "value", ex=100)
            mock_redis.set.assert_awaited_once()

            # Simulate get operation
            mock_redis.get = AsyncMock(return_value="value")
            result = await RedisClient.get("key")
            assert result == "value"
            mock_redis.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_after_set_with_ttl(self):
        """Get retrieves a value that was set with TTL."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_get_client.return_value = mock_redis

            mock_redis.set = AsyncMock()
            mock_redis.get = AsyncMock(return_value="temporary-value")

            await RedisClient.set("temp-key", "temporary-value", ex=60)
            result = await RedisClient.get("temp-key")

            assert result == "temporary-value"
            mock_redis.set.assert_awaited_once_with("temp-key", "temporary-value", 60)


class TestRedisClientErrorHandling:
    """Tests for RedisClient error handling."""

    @pytest.mark.asyncio
    async def test_get_connection_error(self):
        """get propagates connection errors."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_redis.get = AsyncMock(
                side_effect=redis.ConnectionError("Connection failed")
            )
            mock_get_client.return_value = mock_redis

            with pytest.raises(redis.ConnectionError):
                await RedisClient.get("key")

    @pytest.mark.asyncio
    async def test_set_connection_error(self):
        """set propagates connection errors."""
        with patch.object(RedisClient, "get_client") as mock_get_client:
            mock_redis = AsyncMock(spec=redis.Redis)
            mock_redis.set = AsyncMock(
                side_effect=redis.ConnectionError("Connection failed")
            )
            mock_get_client.return_value = mock_redis

            with pytest.raises(redis.ConnectionError):
                await RedisClient.set("key", "value")

    @pytest.mark.asyncio
    async def test_close_connection_error(self):
        """close propagates connection errors gracefully."""
        mock_redis = AsyncMock(spec=redis.Redis)
        mock_redis.close = AsyncMock(
            side_effect=redis.ConnectionError("Connection failed")
        )
        RedisClient._instance = mock_redis

        with pytest.raises(redis.ConnectionError):
            await RedisClient.close()
