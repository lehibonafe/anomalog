from fastapi import APIRouter, Depends, Path, Query, Response

from app.config import Settings, get_settings
from app.schemas.investigations import (
    InvestigationImportRequest,
    InvestigationImportResponse,
    InvestigationListResponse,
    InvestigationWrite,
    SavedInvestigation,
)
from app.services import investigation_history


router = APIRouter(prefix="/api/investigations", tags=["investigations"])
_ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"


@router.get("", response_model=InvestigationListResponse)
def list_investigations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
):
    items, next_offset = investigation_history.list_investigations(
        settings.history_db_path, limit, offset
    )
    return InvestigationListResponse(items=items, next_offset=next_offset)


@router.put("/{investigation_id}", response_model=SavedInvestigation)
def save_investigation(
    record: InvestigationWrite,
    investigation_id: str = Path(pattern=_ID_PATTERN),
    settings: Settings = Depends(get_settings),
):
    return investigation_history.save_investigation(
        settings.history_db_path, investigation_id, record
    )


@router.post("/import", response_model=InvestigationImportResponse)
def import_investigations(
    request: InvestigationImportRequest,
    settings: Settings = Depends(get_settings),
):
    return InvestigationImportResponse(imported=investigation_history.import_investigations(
        settings.history_db_path, request.items
    ))


@router.delete("/{investigation_id}", status_code=204)
def delete_investigation(
    investigation_id: str = Path(pattern=_ID_PATTERN),
    settings: Settings = Depends(get_settings),
):
    investigation_history.delete_investigation(settings.history_db_path, investigation_id)
    return Response(status_code=204)
