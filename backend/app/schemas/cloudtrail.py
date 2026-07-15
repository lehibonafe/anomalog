from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import LogEvent

LookupAttributeKey = Literal[
    "EventId",
    "EventName",
    "ReadOnly",
    "Username",
    "ResourceType",
    "ResourceName",
    "EventSource",
    "AccessKeyId",
]


class CloudTrailSearchRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    lookup_attribute_key: LookupAttributeKey | None = None
    lookup_attribute_value: str | None = None
    limit: int = 1000
    cursor: str | None = None


class CloudTrailSearchResponse(BaseModel):
    events: list[LogEvent]
    cursor: str | None = None
    truncated: bool = False
    total_returned: int = 0
