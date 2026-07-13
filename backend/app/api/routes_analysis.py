from fastapi import APIRouter, Depends

from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.anomaly_service import AnomalyService, get_anomaly_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/anomalies", response_model=AnalysisResponse)
async def analyze_anomalies(
    request: AnalysisRequest,
    service: AnomalyService = Depends(get_anomaly_service),
):
    return await service.analyze(
        request.events,
        request.context,
        provider=request.provider,
        api_key=request.api_key or None,
        model=request.model or None,
        base_url=request.base_url or None,
    )
