from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class User(BaseModel):
    id: int
    authentik_sub: str
    email: str
    username: Optional[str]
    github_username: Optional[str]
    github_access_token: Optional[str]
    github_token_expiry: Optional[datetime]
    last_github_sync: datetime