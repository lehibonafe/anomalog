from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import LogEvent


class LogGroup(BaseModel):
    name: str
    stored_bytes: int | None = None
    creation_time: datetime | None = None


class LogGroupsResponse(BaseModel):
    log_groups: list[LogGroup]
    next_token: str | None = None


class CloudWatchSearchRequest(BaseModel):
    log_group_names: list[str]
    start_time: datetime
    end_time: datetime
    filter_pattern: str | None = None
    limit: int = 1000
    cursor: str | None = None


class CloudWatchSearchResponse(BaseModel):
    events: list[LogEvent]
    cursor: str | None = None
    truncated: bool = False
    total_returned: int = 0
