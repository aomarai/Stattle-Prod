"""
Models for users.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from . import Base


class User(Base):
    """
    SQLAlchemy model for application users.

    Attributes:
        id (int): Primary key.
        authentik_sub (str): Unique Authentik subject identifier.
        email (str): Unique email address.
        username (Optional[str]): Optional username.
        github_username (Optional[str]): Optional unique GitHub username.
        github_access_token (Optional[str]): GitHub access token (should be encrypted at rest).
        github_token_expiry (Optional[datetime]): Expiry date for GitHub token.
        last_github_sync (Optional[datetime]): Last GitHub sync timestamp.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    authentik_sub: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    username: Mapped[Optional[str]]
    github_username: Mapped[Optional[str]] = mapped_column(nullable=True, unique=True)
    github_access_token: Mapped[
        Optional[str]
    ]  # TODO: Use encryption at rest to store the access token
    github_token_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_github_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    def __repr__(self):
        """
        Return a string representation of the User instance.
        """
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
