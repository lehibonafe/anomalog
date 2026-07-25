from functools import lru_cache

import httpx

from app.config import get_settings


@lru_cache
def get_masking_http_client() -> httpx.Client | None:
    settings = get_settings()
    if not settings.masking_service_api_key:
        return None
    return httpx.Client(
        base_url=settings.masking_service_url,
        headers={"X-API-Key": settings.masking_service_api_key},
        timeout=settings.masking_service_timeout_s,
        verify=settings.masking_service_verify_ssl,
    )
