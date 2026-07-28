from openai import AsyncOpenAI

from app.config import Settings
from app.services.llm.base import ProviderDefaults
from app.services.llm.openai_provider import OpenAIProvider

DEFAULT_RPM = 60
DEFAULT_MAX_RETRIES = 2


class LiteLLMProvider(OpenAIProvider):
    """Reuses OpenAIProvider's client and call_chunk as-is (a LiteLLM proxy
    exposes an OpenAI-compatible /v1/chat/completions route) — only
    __init__/resolve_defaults differ. Server-configured like GeminiProvider:
    settings.litellm_api_key/model/base_url are the boot-time defaults (the
    proxy authenticates callers with a virtual key it generates, not the
    underlying provider's own key), frontend overrides win when supplied.
    """

    name = "litellm"

    @classmethod
    def resolve_defaults(cls, settings: Settings) -> ProviderDefaults:
        return ProviderDefaults(
            model=settings.litellm_model,
            rpm=DEFAULT_RPM,
            max_retries=DEFAULT_MAX_RETRIES,
            base_url=settings.litellm_base_url,
        )

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None,
        settings: Settings,
    ) -> None:
        self.client = AsyncOpenAI(
            api_key=api_key or settings.litellm_api_key,
            base_url=base_url or settings.litellm_base_url,
        )
        self.model = model
