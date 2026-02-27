"""
Pydantic schemas for event models.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..models.event import EventSource, EventType


class Event(BaseModel):
    """
    Pydantic schema for event data.

    Attributes:
        id (int): Event ID.
        user_id (int): Foreign key to user table.
        source (EventSource): Source of the event.
        type (EventType): Type of the event.
        data (dict): Raw event data.
        occurred_at (datetime): When the event occurred.
        ingested_at (datetime): When the event was ingested.
        github_event_id (str): Unique event ID from GitHub (if applicable).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    source: EventSource
    type: EventType
    data: dict
    occurred_at: datetime
    ingested_at: datetime
    github_event_id: str
