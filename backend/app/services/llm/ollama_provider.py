import openai
from openai import AsyncOpenAI

from app.config import Settings
from app.core.errors import LLMRequestError
from app.schemas.analysis import ChunkResult
from app.services.llm.base import LLMRateLimited, ProviderDefaults
from app.services.llm.openai_provider import OpenAIProvider

DEFAULT_MODEL = "llama3.1"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_RPM = 6000  # local inference, effectively unpaced
DEFAULT_MAX_RETRIES = 0  # no cloud quota to back off against


class OllamaProvider(OpenAIProvider):
    """Reuses OpenAIProvider's client (Ollama's /v1/chat/completions is
    OpenAI-compatible) but overrides call_chunk: Ollama's compat layer does not
    reliably honor response_format={"type":"json_schema","strict":true}
    (github.com/ollama/ollama/issues/10001), so this uses plain JSON mode
    (response_format={"type":"json_object"}) plus the schema embedded in the
    prompt by build_prompt(), and parses the result manually.
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

    async def call_chunk(self, prompt: str) -> ChunkResult:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except openai.RateLimitError as e:
            raise LLMRateLimited(str(e)) from e
        except Exception as e:
            raise LLMRequestError(str(e)) from e

        content = completion.choices[0].message.content
        if not content:
            raise LLMRequestError("Ollama returned an empty response")
        try:
            return ChunkResult.model_validate_json(content)
        except Exception as e:
            raise LLMRequestError(f"Ollama response did not match the expected schema: {e}") from e
