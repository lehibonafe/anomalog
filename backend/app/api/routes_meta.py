from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.masking import mask_message

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


class MaskTestRequest(BaseModel):
    lines: list[str]


class MaskTestResponse(BaseModel):
    masked: list[str]


@router.post("/mask/test", response_model=MaskTestResponse)
def mask_test(body: MaskTestRequest):
    """Dev-only: run the local regex masker on posted text, bypassing AWS.

    For manually verifying mask_message() coverage via curl.
    """
    return MaskTestResponse(masked=[mask_message(line) for line in body.lines])


@router.get("/config")
def config(settings: Settings = Depends(get_settings)):
    return {
        "aws_region": settings.aws_region,
        "litellm_configured": bool(settings.litellm_api_key),
        "litellm_model": settings.litellm_model,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.gemini_model,
        "max_log_search_lines": settings.max_log_search_lines,
        "max_analysis_lines": settings.max_analysis_lines,
    }
