"""
Module for interacting with the GitHub API to fetch user information.
"""

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
            "Authorization": f"Bearer {token}",
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

    async def get(self, endpoint: str, params: dict = None, **kwargs) -> Union[dict[str, Any], list[Any]]:
        """
        Performs a GET request to the specified GitHub API endpoint.

        :param endpoint: The API endpoint to fetch data from (e.g., ``"users/{username}"``).
        :param params: Optional query parameters for the request.
        :param kwargs: Additional keyword arguments (e.g., ``paginate=True``).
        :raises httpx.HTTPStatusError: If the response status code indicates an error.
        :return: API response data. Without pagination, returns a dict. With ``paginate=True``, returns
            a list of all paginated results.
        """
        url = f"{self.base_url}/{endpoint}"
        client = await self.get_client()

        if not kwargs.get("paginate", False):
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        else:
            results = []
            while url:
                response = await client.get(
                    url, headers=self.headers, params=params
                )
                response.raise_for_status()
                results.extend(response.json())

                # Check if next page exists
                link = response.headers.get("Link")
                next_url = None
                if link:
                    for part in link.split(","):
                        if 'rel="next"' in part:
                            next_url = part[part.find("<") + 1 : part.find(">")]
                            break
                url = next_url
                params = {}
            return results

    async def get_user_info(self) -> dict[str, Any]:
        """
        Retrieve information about the current user.
        """
        return await self.get("user")

    async def get_user_events(self, username: str, per_page: int = 100) -> list[dict[str, Any]]:
        """
        Retrieve the events related to a specific user.
        :param username: GitHub username of the user.
        :param per_page: Number of events per page to request from GitHub (pagination page size).
        :return: List of all events related to a specific user.
        """
        return await self.get(
            f"users/{username}/events",
            params={"per_page": per_page},
            paginate=True,
        )