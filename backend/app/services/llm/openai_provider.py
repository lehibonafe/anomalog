import openai
from openai import AsyncOpenAI

from app.config import Settings
from app.core.errors import BadRequestError, LLMRequestError
from app.schemas.analysis import ChunkResult
from app.services.llm.base import LLMProvider, LLMRateLimited, ProviderDefaults

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_RPM = 60
DEFAULT_MAX_RETRIES = 2


class OpenAIProvider(LLMProvider):
    name = "openai"

    @classmethod
    def resolve_defaults(cls, settings: Settings) -> ProviderDefaults:
        return ProviderDefaults(
            model=DEFAULT_MODEL, rpm=DEFAULT_RPM, max_retries=DEFAULT_MAX_RETRIES, base_url=None
        )

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None,
        settings: Settings,
    ) -> None:
        if not api_key:
            raise BadRequestError(
                "OpenAI provider requires an api_key (set it in Model settings)."
            )
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def call_chunk(self, prompt: str) -> ChunkResult:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
        except openai.RateLimitError as e:
            raise LLMRateLimited(str(e)) from e
        except (openai.APIStatusError, openai.APIConnectionError) as e:
            raise LLMRequestError(str(e)) from e
        except Exception as e:
            raise LLMRequestError(str(e)) from e

        message = completion.choices[0].message
        if message.refusal:
            raise LLMRequestError(f"Model refused: {message.refusal}")
        if not message.content:
            raise LLMRequestError("Model returned an empty response")
        return ChunkResult(analysis=message.content)
