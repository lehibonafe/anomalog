from openai import AsyncOpenAI

from app.config import Settings
from app.services.llm.base import ProviderDefaults
from app.services.llm.openai_provider import OpenAIProvider

DEFAULT_MODEL = "llama3.1"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_RPM = 6000  # local inference, effectively unpaced
DEFAULT_MAX_RETRIES = 0  # no cloud quota to back off against


class OllamaProvider(OpenAIProvider):
    """Reuses OpenAIProvider's client and call_chunk as-is (Ollama's
    /v1/chat/completions is OpenAI-compatible, and both now just return plain
    text) — only __init__/resolve_defaults differ, to supply Ollama's
    localhost base_url and to not require an api_key.
    """

    name = "ollama"

    @classmethod
    def resolve_defaults(cls, settings: Settings) -> ProviderDefaults:
        return ProviderDefaults(
            model=DEFAULT_MODEL,
            rpm=DEFAULT_RPM,
            max_retries=DEFAULT_MAX_RETRIES,
            base_url=DEFAULT_BASE_URL,
        )

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None,
        settings: Settings,
    ) -> None:
        # api_key is required by the SDK constructor but ignored by Ollama.
        self.client = AsyncOpenAI(api_key=api_key or "ollama", base_url=base_url or DEFAULT_BASE_URL)
        self.model = model
