"""
Models for events and related enums for event tracking.

Classes:
    EventSource (Enum): Enum for event sources (GitHub, GitLab, Bitbucket).
    EventType (Enum): Enum for event types (commit, pull request, issue, comment).
    Event (Base): SQLAlchemy model for storing raw events from external sources.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from . import Base


class EventSource(Enum):
    """
    Enum representing the source of the event.

    Attributes:
        GITHUB: Event from GitHub.
        GITLAB: Event from GitLab.
        BITBUCKET: Event from Bitbucket.
    """

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class EventType(Enum):
    """
    Enum representing the type of the event.

    Attributes:
        COMMIT: Commit event.
        PULL_REQUEST: Pull request event.
        ISSUE: Issue event.
        COMMENT: Comment event.
    """

    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    COMMENT = "comment"


class Event(Base):
    """
    SQLAlchemy model for storing raw events from external sources such as GitHub.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to user table.
        source (EventSource): Source of the event.
        type (EventType): Type of the event.
        data (dict): Raw event data (JSON).
        occurred_at (datetime): When the event occurred.
        ingested_at (datetime): When the event was ingested.
        github_event_id (str): Unique event ID from GitHub (if applicable).
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
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )
    github_event_id: Mapped[str] = mapped_column(index=True, nullable=True, unique=True)
