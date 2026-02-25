"""
Pydantic schema for user models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, PrivateAttr, ConfigDict


class User(BaseModel):
    """
    Pydantic schema for user data.

    Attributes:
        id (int): User ID.
        authentik_sub (str): Unique Authentik subject identifier.
        email (str): User email address.
        username (Optional[str]): Optional username.
        github_username (Optional[str]): Optional GitHub username.
        github_access_token (Optional[str]): GitHub access token (private attribute).
        github_token_expiry (Optional[datetime]): Expiry date for GitHub token.
        last_github_sync (Optional[datetime]): Last GitHub sync timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    authentik_sub: str
    email: str
    username: Optional[str]
    github_username: Optional[str]
    github_access_token: Optional[str] = PrivateAttr(default="secret")
    github_token_expiry: Optional[datetime]
    last_github_sync: Optional[datetime]
