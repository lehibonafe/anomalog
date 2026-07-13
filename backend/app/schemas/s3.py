from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import LogEvent


class S3Bucket(BaseModel):
    name: str
    creation_date: datetime | None = None


class S3BucketsResponse(BaseModel):
    buckets: list[S3Bucket]


class S3Object(BaseModel):
    key: str
    size: int
    last_modified: datetime


class S3ObjectsResponse(BaseModel):
    objects: list[S3Object]
    continuation_token: str | None = None


class S3ContentRequest(BaseModel):
    bucket: str
    keys: list[str]


class S3ObjectContentInfo(BaseModel):
    key: str
    byte_size: int
    truncated: bool
    line_count: int


class S3ContentResponse(BaseModel):
    events: list[LogEvent]
    objects: list[S3ObjectContentInfo]
    truncated_overall: bool = False
