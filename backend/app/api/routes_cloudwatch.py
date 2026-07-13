from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.schemas.cloudwatch import (
    CloudWatchSearchRequest,
    CloudWatchSearchResponse,
    LogGroupsResponse,
)
from app.services import cloudwatch_service

router = APIRouter(prefix="/api/cloudwatch", tags=["cloudwatch"])


@router.get("/log-groups", response_model=LogGroupsResponse)
def get_log_groups(
    prefix: str | None = Query(default=None),
    next_token: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=50),
):
    return cloudwatch_service.list_log_groups(prefix, next_token, limit)


@router.post("/logs/search", response_model=CloudWatchSearchResponse)
def search_logs(
    request: CloudWatchSearchRequest,
    settings: Settings = Depends(get_settings),
):
    return cloudwatch_service.search_log_events(
        log_group_names=request.log_group_names,
        start_time=request.start_time,
        end_time=request.end_time,
        filter_pattern=request.filter_pattern,
        limit=request.limit,
        cursor=request.cursor,
        settings=settings,
    )
