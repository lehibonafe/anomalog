import openai
from openai import AsyncOpenAI

from app.config import Settings
from app.core.errors import BadRequestError, LLMRequestError
from app.schemas.analysis import ChunkResult
from app.services.llm.base import DEFAULT_LLM_TIMEOUT_S, LLMProvider, LLMRateLimited, ProviderDefaults

DEFAULT_MODEL = "gpt-6-sol"
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
        self.client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=DEFAULT_LLM_TIMEOUT_S, max_retries=0
        )
        self.model = model
        self.max_output_tokens = settings.max_llm_output_tokens
        self.extra_body: dict[str, object] | None = None

    async def call_chunk(self, system: str, prompt: str) -> ChunkResult:
        try:
            request: dict[str, object] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
            if self.model.lower().startswith("gpt-6-"):
                # GPT-6 reasoning models reject sampling parameters. Low effort
                # suits the short, latency-sensitive incident-analysis answers.
                request["reasoning_effort"] = "low"
                request["max_completion_tokens"] = self.max_output_tokens
            else:
                request["temperature"] = 0.1
                request["max_tokens"] = self.max_output_tokens
            extra_body = getattr(self, "extra_body", None)
            if extra_body:
                request["extra_body"] = extra_body
            completion = await self.client.chat.completions.create(  # type: ignore[arg-type]
                **request,
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
