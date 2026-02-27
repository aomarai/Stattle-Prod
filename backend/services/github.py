"""
Module for interacting with the GitHub API to fetch user information.
"""

import asyncio
import re
import utils.logging
from datetime import datetime
from typing import Any, Optional, Union

import httpx

from utils.redis_client import RedisClient

logger = utils.logging.get_logger(__name__)


class GitHubService:
    """
    A class to interact with the GitHub API.
    """

    _client: Optional[httpx.AsyncClient] = None
    _lock = asyncio.Lock()

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

    async def _get_current_rate_limit(
        self,
    ) -> None:  # TODO: Finish redis stuff for github service
        remaining = await RedisClient.get("github:rate_limit:remaining")
        reset_time = await RedisClient.get("github:rate_limit:reset_time")

        if remaining and int(remaining) < 10:
            if reset_time:
                wait_seconds = int(reset_time) - int(datetime.now().timestamp())
                if wait_seconds > 0:
                    logger.warning(
                        f"Rate limit exceeded. Reset time: {reset_time}. Sleeping for {wait_seconds} seconds."
                    )
                    await asyncio.sleep(wait_seconds)

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
        url = f"{self.base_url}/{endpoint}"
        client = await self.get_client()

        if not paginate:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

        results = []
        current_params = params or {}
        while url:
            response = await client.get(
                url, headers=self.headers, params=current_params
            )
            response.raise_for_status()
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
