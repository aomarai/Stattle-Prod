from datetime import datetime
from pydantic import BaseModel, ConfigDict

from ..models.event import EventSource, EventType


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    source: EventSource
    type: EventType
    data: dict
    occurred_at: datetime
    ingested_at: datetime
    github_event_id: str
