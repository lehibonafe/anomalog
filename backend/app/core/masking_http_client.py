import logging
from functools import lru_cache

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_masking_http_client() -> httpx.Client | None:
    settings = get_settings()
    if not settings.masking_service_api_key:
        return None
    if not settings.masking_service_verify_ssl:
        logger.warning(
            "TLS certificate verification is disabled for the masking service "
            "(%s) — PII-masking traffic is vulnerable to MITM. Set "
            "MASKING_SERVICE_VERIFY_SSL=true once a trusted cert is issued.",
            settings.masking_service_url,
        )
    return httpx.Client(
        base_url=settings.masking_service_url,
        headers={"X-API-Key": settings.masking_service_api_key},
        timeout=settings.masking_service_timeout_s,
        verify=settings.masking_service_verify_ssl,
    )
