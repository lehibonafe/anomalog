from app.config import Settings
from app.core.errors import BadRequestError


def approved_model_base_url(
    provider: str, requested: str | None, default: str | None, settings: Settings
) -> str | None:
    """Permit only the provider's server-approved destinations."""
    if requested is None:
        return default
    if provider == "gemini":
        raise BadRequestError("Gemini does not accept a custom base_url.")
    if requested == default or requested in settings.model_base_url_allowlist.get(provider, []):
        return requested
    raise BadRequestError("Model base_url is not approved for this provider.")
