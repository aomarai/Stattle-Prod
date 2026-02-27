"""
Module for interacting with the GitHub API to fetch user information.
"""

import re
from typing import Any, Optional, Union

import httpx


class GitHubService:
    """
    A class to interact with the GitHub API.
    """

    _client: Optional[httpx.AsyncClient] = None

    def __init__(self, token: str):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None:
            cls._client = httpx.AsyncClient()
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

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
        self, endpoint: str, params: Optional[dict[str, Any]] = None, **kwargs
    ) -> Union[dict[str, Any], list[Any]]:
        """
        Performs a GET request to the specified GitHub API endpoint.
        :param endpoint: Endpoint to be requested.
        :param params: Additional query parameters.
        :param kwargs: Additional query parameters.

        :raise httpx.HTTPError: HTTP error.

        :return: Response from GitHub API.

        """
        url = f"{self.base_url}/{endpoint}"
        client = await self.get_client()

        if not kwargs.get("paginate", False):
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
