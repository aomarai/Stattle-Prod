from datetime import datetime
from typing import Optional

from pydantic import BaseModel, PrivateAttr, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    authentik_sub: str
    email: str
    username: Optional[str]
    github_username: Optional[str]
    github_access_token: Optional[str] = PrivateAttr(default="secret")
    github_token_expiry: Optional[datetime]
    last_github_sync: Optional[datetime]
