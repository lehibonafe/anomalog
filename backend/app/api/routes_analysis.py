from fastapi import APIRouter, Depends

from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
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
        user_prompt=request.user_prompt or None,
    )


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    request: TestConnectionRequest,
    service: AnomalyService = Depends(get_anomaly_service),
):
    return await service.test_connection(
        provider=request.provider,
        api_key=request.api_key or None,
        model=request.model or None,
        base_url=request.base_url or None,
    )
