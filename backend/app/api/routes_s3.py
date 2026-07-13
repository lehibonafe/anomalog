from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.schemas.s3 import (
    S3BucketsResponse,
    S3ContentRequest,
    S3ContentResponse,
    S3ObjectsResponse,
)
from app.services import s3_service

router = APIRouter(prefix="/api/s3", tags=["s3"])


@router.get("/buckets", response_model=S3BucketsResponse)
def get_buckets():
    return s3_service.list_buckets()


@router.get("/objects", response_model=S3ObjectsResponse)
def get_objects(
    bucket: str,
    prefix: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    continuation_token: str | None = Query(default=None),
    max_keys: int = Query(default=500, ge=1, le=1000),
):
    return s3_service.list_objects(
        bucket, prefix, start, end, continuation_token, max_keys
    )


@router.post("/objects/content", response_model=S3ContentResponse)
def get_object_content(
    request: S3ContentRequest,
    settings: Settings = Depends(get_settings),
):
    return s3_service.fetch_object_content(request.bucket, request.keys, settings)
