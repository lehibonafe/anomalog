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

CloudTrailAccountId = Literal[
    "887350548529",
    "065031412132",
    "221315724874",
    "550222016520",
    "679437835821",
    "765186506449",
]


class CloudTrailSearchRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    account_id: CloudTrailAccountId | None = None
    lookup_attribute_key: LookupAttributeKey | None = None
    lookup_attribute_value: str | None = None
    limit: int = 1000
    cursor: str | None = None


class CloudTrailSearchResponse(BaseModel):
    events: list[LogEvent]
    cursor: str | None = None
    truncated: bool = False
    total_returned: int = 0
