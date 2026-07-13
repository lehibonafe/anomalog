import anthropic

from app.config import Settings
from app.core.errors import BadRequestError, LLMRequestError
from app.schemas.analysis import ChunkResult
from app.services.llm.base import LLMProvider, LLMRateLimited, ProviderDefaults

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_RPM = 50
DEFAULT_MAX_RETRIES = 2

_TOOL_NAME = "report_findings"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

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
                "Anthropic provider requires an api_key (set it in Model settings)."
            )
        self.client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self.model = model

    async def call_chunk(self, prompt: str) -> ChunkResult:
        tool = {
            "name": _TOOL_NAME,
            "description": "Report the anomaly findings extracted from this log chunk.",
            "input_schema": ChunkResult.model_json_schema(),
        }
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.RateLimitError as e:
            raise LLMRateLimited(str(e)) from e
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            raise LLMRequestError(str(e)) from e
        except Exception as e:
            raise LLMRequestError(str(e)) from e

        for block in response.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                return ChunkResult.model_validate(block.input)
        raise LLMRequestError("Anthropic response did not contain the expected tool call")
