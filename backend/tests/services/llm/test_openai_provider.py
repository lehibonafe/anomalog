from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from app.config import Settings
from app.core.errors import BadRequestError, LLMRequestError
from app.schemas.analysis import ChunkResult, Finding
from app.services.llm.base import LLMRateLimited
from app.services.llm.openai_provider import OpenAIProvider


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


def make_provider(api_key: str | None = "test-openai-key") -> OpenAIProvider:
    settings = make_settings()
    return OpenAIProvider(api_key=api_key, model="gpt-4o-mini", base_url=None, settings=settings)


def make_rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def test_requires_api_key():
    with pytest.raises(BadRequestError):
        make_provider(api_key=None)


async def test_call_chunk_returns_parsed_result():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.refusal = None
    fake_message.parsed = ChunkResult(
        findings=[
            Finding(
                id="f1",
                severity="critical",
                category="error",
                line_index_start=0,
                line_index_end=0,
                excerpt="x",
                explanation="y",
            )
        ]
    )
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.parse = AsyncMock(return_value=fake_completion)

    result = await provider.call_chunk("prompt")

    assert len(result.findings) == 1
    assert result.findings[0].id == "f1"


async def test_call_chunk_raises_request_error_on_refusal():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.refusal = "cannot help with that"
    fake_message.parsed = None
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.parse = AsyncMock(return_value=fake_completion)

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("prompt")


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    provider.client.chat.completions.parse = AsyncMock(side_effect=make_rate_limit_error())

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("prompt")
