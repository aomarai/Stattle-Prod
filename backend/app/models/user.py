from datetime import datetime
from models import Base
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime
from typing import Optional


class User(Base):
    __tablename__ = "user"
    
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        index=True
    )
    authentik_sub: Mapped[str] = mapped_column(
        nullable=False,
        unique=True,
        index=True
    )
    email: Mapped[str] = mapped_column(
        nullable=False,
        unique=True,
        index=True
    )
    username: Mapped[Optional[str]]
    github_username: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        unique=True
    )
    github_access_token: Mapped[Optional[str]]
    github_token_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_github_sync: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"