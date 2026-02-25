from datetime import datetime
from enum import Enum
from . import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime
from sqlalchemy import Enum as SQLEnum


class EventSource(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class EventType(Enum):
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    COMMENT = "comment"


class Event(Base):
    """
    Raw event from Github.

    Do not delete from this table.
    """

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    source: Mapped[EventSource] = mapped_column(SQLEnum(EventSource), nullable=False)
    type: Mapped[EventType] = mapped_column(SQLEnum(EventType), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB)  # Entire event from Github
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    github_event_id: Mapped[str] = mapped_column(index=True, nullable=True, unique=True)
