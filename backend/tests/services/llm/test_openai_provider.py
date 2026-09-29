from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from app.config import Settings
from app.core.errors import BadRequestError, LLMRequestError
from app.services.llm.base import LLMRateLimited
from app.services.llm.openai_provider import DEFAULT_MODEL, OpenAIProvider


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", **overrides)


def make_provider(
    api_key: str | None = "test-openai-key", model: str = DEFAULT_MODEL
) -> OpenAIProvider:
    settings = make_settings()
    return OpenAIProvider(api_key=api_key, model=model, base_url=None, settings=settings)


def make_rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def test_requires_api_key():
    with pytest.raises(BadRequestError):
        make_provider(api_key=None)


def test_recommended_default_model():
    defaults = OpenAIProvider.resolve_defaults(make_settings())

    assert defaults.model == "gpt-6-sol"


async def test_call_chunk_returns_text_result():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.refusal = None
    fake_message.content = "line [0] looks fine."
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    result = await provider.call_chunk("system prompt", "prompt")

    assert result.analysis == "line [0] looks fine."
    request = provider.client.chat.completions.create.await_args.kwargs
    assert "extra_body" not in request
    assert "temperature" not in request
    assert request["reasoning_effort"] == "low"
    assert request["max_completion_tokens"] == 2048


async def test_legacy_model_keeps_sampling_and_max_tokens():
    provider = make_provider(model="gpt-4o-mini")
    fake_message = MagicMock(refusal=None, content="legacy response")
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    await provider.call_chunk("system prompt", "prompt")

    request = provider.client.chat.completions.create.await_args.kwargs
    assert request["temperature"] == 0.1
    assert request["max_tokens"] == 2048


async def test_call_chunk_raises_request_error_on_refusal():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.refusal = "cannot help with that"
    fake_message.content = None
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("system prompt", "prompt")


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    provider.client.chat.completions.create = AsyncMock(side_effect=make_rate_limit_error())

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("system prompt", "prompt")
