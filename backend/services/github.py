"""
Module for interacting with the GitHub API to fetch user information.
"""

import asyncio
import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union

import httpx

import utils.logging
from utils.redis_client import RedisClient

logger = utils.logging.get_logger(__name__)


class GitHubRedisNamespace(Enum):
    """Base namespace for GitHub Redis keys."""

    GITHUB = "github"
    RATE_LIMIT = "rate_limit"


class GitHubRateLimitKey(Enum):
    """Rate limit properties."""

    REMAINING = "remaining"
    RESET = "reset"
    LIMIT = "limit"

    def full_key(self) -> str:
        """Get the full Redis key."""
        return f"{GitHubRedisNamespace.GITHUB.value}:{GitHubRedisNamespace.RATE_LIMIT.value}:{self.value}"


class GitHubService:
    """
    A class to interact with the GitHub API.
    """

    _client: Optional[httpx.AsyncClient] = None
    _lock = asyncio.Lock()

    LUA_UPDATE_RATE_LIMIT = """
        local timestamp_key = KEYS[1]
        local current_timestamp = tonumber(ARGV[1])
        local stored_timestamp = redis.call('GET', timestamp_key)

        if not stored_timestamp or tonumber(stored_timestamp) <= current_timestamp then
            redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
            redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[2])
            if ARGV[4] ~= '' then redis.call('SET', KEYS[3], ARGV[4], 'EX', ARGV[2]) end
            if ARGV[5] ~= '' then redis.call('SET', KEYS[4], ARGV[5], 'EX', ARGV[2]) end
            return 1
        end
        return 0
        """

    def __init__(self, token: str):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """
        Get or create a singleton AsyncClient instance.

        Returns:
            httpx.AsyncClient: The shared AsyncClient instance.
        """
        async with cls._lock:
            if cls._client is None:
                cls._client = httpx.AsyncClient()
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        """
        Close the singleton AsyncClient instance if it exists.
        """
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

    async def _check_rate_limit(
        self,
    ) -> None:
        """
        Check the current rate limit usage for the GitHub API.
        If the rate limit is exceeded, sleeps until the rate limit resets.

        :return: None
        """
        remaining = await RedisClient.get(GitHubRateLimitKey.REMAINING.full_key())
        reset_time = await RedisClient.get(GitHubRateLimitKey.RESET.full_key())

        if remaining and int(remaining) < 10:
            if reset_time:
                wait_seconds = int(reset_time) - int(datetime.now().timestamp())
                if wait_seconds > 0:
                    logger.warning(
                        f"Rate limit approaching limit. Reset time: {reset_time}. Sleeping for {wait_seconds} seconds."
                    )
                    await asyncio.sleep(wait_seconds + 1)

    async def _update_rate_limit(self, response: httpx.Response) -> None:
        """Update rate limit atomically using a Redis Lua script."""
        if "X-RateLimit-Reset" not in response.headers:
            return

        reset_time = int(response.headers["X-RateLimit-Reset"])
        ttl = max(reset_time - int(datetime.now().timestamp()), 60)
        current_timestamp = datetime.now().timestamp()

        remaining = response.headers.get("X-RateLimit-Remaining", "")
        limit = response.headers.get("X-RateLimit-Limit", "")

        client = await RedisClient.get_client()

        await client.eval(
            self.LUA_UPDATE_RATE_LIMIT,
            4,
            f"{GitHubRedisNamespace.GITHUB.value}:{GitHubRedisNamespace.RATE_LIMIT.value}:timestamp",
            GitHubRateLimitKey.RESET.full_key(),
            GitHubRateLimitKey.REMAINING.full_key(),
            GitHubRateLimitKey.LIMIT.full_key(),
            str(current_timestamp),
            str(ttl),
            str(reset_time),
            remaining,
            limit,
        )

    @staticmethod
    def _extract_next_url(link_header: Optional[str]) -> Optional[str]:
        """
        Extracts the next URL from the link header.
        :param link_header: Link header from GitHub API.
        :return: The next URL from the link header.s
        """
        if not link_header:
            return None

        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        return match.group(1) if match else None

    async def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        paginate: bool = False,
    ) -> Union[dict[str, Any], list[Any]]:
        """
        Performs a GET request to the specified GitHub API endpoint.
        :param endpoint: Endpoint to be requested.
        :param params: Additional query parameters.
        :param paginate: Whether to perform pagination during request.

        :raise httpx.HTTPError: HTTP error.

        :return: Response from GitHub API.

        """
        await self._check_rate_limit()

        url = f"{self.base_url}/{endpoint}"
        client = await self.get_client()

        if not paginate:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            await self._update_rate_limit(response)
            return response.json()

        results = []
        current_params = params or {}
        while url:
            response = await client.get(
                url, headers=self.headers, params=current_params
            )
            response.raise_for_status()
            await self._update_rate_limit(response)
            results.extend(response.json())

            # Check if next page exists
            url = self._extract_next_url(response.headers.get("Link"))
            current_params = {}  # Next URL already contains query params
        return results

    async def get_user_info(self) -> dict[str, Any]:
        """
        Retrieve information about the current user.
        """
        return await self.get("user")

    async def get_user_events(
        self, username: str, per_page: int = 100
    ) -> list[dict[str, Any]]:
        """
        Retrieve the events related to a specific user.
        :param username: GitHub username of the user.
        :param per_page: Number of events per page.
        :return: List of events related to a specific user.
        """
        return await self.get(
            f"users/{username}/events", params={"per_page": per_page}, paginate=True
        )
