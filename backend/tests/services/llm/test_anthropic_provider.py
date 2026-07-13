from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest

from app.config import Settings
from app.core.errors import BadRequestError, LLMRequestError
from app.services.llm.base import LLMRateLimited
from app.services.llm.anthropic_provider import AnthropicProvider


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


def make_provider(api_key: str | None = "test-anthropic-key") -> AnthropicProvider:
    settings = make_settings()
    return AnthropicProvider(
        api_key=api_key, model="claude-haiku-4-5-20251001", base_url=None, settings=settings
    )


def make_rate_limit_error() -> anthropic.RateLimitError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=429, request=request)
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def test_requires_api_key():
    with pytest.raises(BadRequestError):
        make_provider(api_key=None)


async def test_call_chunk_returns_parsed_result_from_tool_use_block():
    provider = make_provider()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "report_findings"
    tool_block.input = {
        "findings": [
            {
                "id": "f1",
                "severity": "critical",
                "category": "error",
                "line_index_start": 0,
                "line_index_end": 0,
                "excerpt": "x",
                "explanation": "y",
            }
        ]
    }
    fake_response = MagicMock()
    fake_response.content = [tool_block]
    provider.client.messages.create = AsyncMock(return_value=fake_response)

    result = await provider.call_chunk("prompt")

    assert len(result.findings) == 1
    assert result.findings[0].id == "f1"


async def test_call_chunk_raises_request_error_when_no_tool_use_block():
    provider = make_provider()
    text_block = MagicMock()
    text_block.type = "text"
    fake_response = MagicMock()
    fake_response.content = [text_block]
    provider.client.messages.create = AsyncMock(return_value=fake_response)

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("prompt")


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    provider.client.messages.create = AsyncMock(side_effect=make_rate_limit_error())

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("prompt")
