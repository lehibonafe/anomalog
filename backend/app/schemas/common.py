from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LogEvent(BaseModel):
    source: Literal["cloudwatch", "s3"]
    origin: str
    stream_or_key: str
    timestamp: datetime | None = None
    message: str
    line_index: int


class TimeRange(BaseModel):
    start: datetime
    end: datetime
