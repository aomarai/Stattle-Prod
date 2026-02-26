"""
Module for interacting with the GitHub API to fetch user information.
"""

from typing import Any

import httpx


class GitHubService:
    """
    A class to interact with the Github API.
    """

    def __init__(self, token: str):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async def get(self, endpoint: str, params: dict = None, **kwargs) -> list[Any]:
            """
            Performs a GET request to the specified GitHub API endpoint.
            Args:
                endpoint: The API endpoint to fetch data from (e.g., 'users/{username}').
                params: Optional query parameters for the request.
                **kwargs: Additional keyword arguments (e.g., pagination).

            Raises: Httpx.HTTPStatusError: If the response status code indicates an error.

            Returns: A list of results from the API response. If pagination is enabled, it will return a combined list of results from all pages.

            """
            url = f"{self.base_url}/{endpoint}"

            if not kwargs.get("pagination"):
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    return response.json()  # TODO: Double check if this returns a list
            else:
                results = []
                async with httpx.AsyncClient() as client:
                    while url:
                        response = await client.get(
                            url, headers=self.headers, params=params
                        )
                        response.raise_for_status()
                        results.extend(response.json())

                        # Check if next page exists
                        link = response.headers.get("Link")
                        if link:
                            for part in link.split(";"):
                                if 'rel="next"' in part:
                                    url = part[part.find("<") + 1 : part.find(">")]
                                    break
                        params = {}
                return results
