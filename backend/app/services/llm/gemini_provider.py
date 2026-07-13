from google import genai
from google.genai import types

from app.config import Settings
from app.core.errors import LLMRequestError
from app.schemas.analysis import ChunkResult
from app.services.llm.base import LLMProvider, LLMRateLimited, ProviderDefaults


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
        self.client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self.model = model

    async def call_chunk(self, prompt: str) -> ChunkResult:
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ChunkResult,
                    temperature=0.1,
                ),
            )
            return ChunkResult.model_validate_json(resp.text)
        except genai.errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                raise LLMRateLimited(str(e)) from e
            raise LLMRequestError(str(e)) from e
        except Exception as e:
            raise LLMRequestError(str(e)) from e
