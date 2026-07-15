from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.cloudtrail import CloudTrailSearchRequest, CloudTrailSearchResponse
from app.services import cloudtrail_service

router = APIRouter(prefix="/api/cloudtrail", tags=["cloudtrail"])


@router.post("/events/search", response_model=CloudTrailSearchResponse)
def search_events(
    request: CloudTrailSearchRequest,
    settings: Settings = Depends(get_settings),
):
    return cloudtrail_service.lookup_events(
        start_time=request.start_time,
        end_time=request.end_time,
        lookup_attribute_key=request.lookup_attribute_key,
        lookup_attribute_value=request.lookup_attribute_value,
        limit=request.limit,
        cursor=request.cursor,
        settings=settings,
    )
