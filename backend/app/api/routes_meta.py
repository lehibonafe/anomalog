from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/config")
def config(settings: Settings = Depends(get_settings)):
    return {
        "aws_region": settings.aws_region,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.gemini_model,
        "max_log_search_lines": settings.max_log_search_lines,
        "max_analysis_lines": settings.max_analysis_lines,
    }
