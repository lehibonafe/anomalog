from secrets import compare_digest

from app.config import Settings


def valid_api_key(candidate: str | None, settings: Settings) -> bool:
    configured = settings.anomalog_api_key
    if configured is None:
        return not settings.require_api_key
    return candidate is not None and compare_digest(
        candidate, configured.get_secret_value()
    )
