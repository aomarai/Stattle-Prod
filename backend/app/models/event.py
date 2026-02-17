from datetime import datetime
from enum import Enum
from models import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime


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
    __tablename__ = "event"
    
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id")
    )
    source: Mapped[EventSource]
    type: Mapped[EventType]
    data: Mapped[JSONB]
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now()
    )
    github_event_id: Mapped[str] = mapped_column(
        nullable=True,
        unique=True
    )
    