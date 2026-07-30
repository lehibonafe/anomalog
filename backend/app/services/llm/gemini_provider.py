from google import genai
from google.genai import types

from app.config import Settings
from app.core.errors import LLMRequestError
from app.schemas.analysis import ChunkResult
from app.services.llm.base import DEFAULT_LLM_TIMEOUT_S, LLMProvider, LLMRateLimited, ProviderDefaults


class GeminiProvider(LLMProvider):
    name = "gemini"

    @classmethod
    def resolve_defaults(cls, settings: Settings) -> ProviderDefaults:
        return ProviderDefaults(
            model=settings.gemini_model,
            rpm=settings.gemini_rpm_limit,
            max_retries=settings.gemini_max_retries,
            base_url=None,
        )

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None,
        settings: Settings,
    ) -> None:
        self.client = genai.Client(
            api_key=api_key or settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(DEFAULT_LLM_TIMEOUT_S * 1000)),
        )
        self.model = model

    async def call_chunk(self, system: str, prompt: str) -> ChunkResult:
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1, system_instruction=system),
            )
            return ChunkResult(analysis=resp.text)
        except genai.errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                raise LLMRateLimited(str(e)) from e
            raise LLMRequestError(str(e)) from e
        except Exception as e:
            raise LLMRequestError(str(e)) from e
