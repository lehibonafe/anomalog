from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from app.config import Settings
from app.core.errors import LLMRequestError
from app.services.llm.base import LLMRateLimited
from app.services.llm.litellm_provider import LiteLLMProvider


def make_settings(**overrides) -> Settings:
    overrides.setdefault("litellm_api_key", "test-litellm-key")
    return Settings(gemini_api_key="test-key", **overrides)


def make_provider(
    api_key: str | None = "sk-litellm-key",
    base_url: str | None = None,
    settings: Settings | None = None,
) -> LiteLLMProvider:
    settings = settings or make_settings()
    return LiteLLMProvider(api_key=api_key, model="qwen3:4b", base_url=base_url, settings=settings)


def test_uses_settings_api_key_when_omitted():
    settings = make_settings(litellm_api_key="from-settings-key")
    provider = make_provider(api_key=None, settings=settings)

    assert provider.client.api_key == "from-settings-key"


def test_overridden_api_key_wins_over_settings():
    settings = make_settings(litellm_api_key="from-settings-key")
    provider = make_provider(api_key="from-frontend-key", settings=settings)

    assert provider.client.api_key == "from-frontend-key"


def test_defaults_base_url_from_settings_when_omitted():
    settings = make_settings(litellm_base_url="https://team-proxy.example.com/v1")
    provider = make_provider(base_url=None, settings=settings)

    assert str(provider.client.base_url).rstrip("/") == "https://team-proxy.example.com/v1"


def test_uses_overridden_base_url():
    settings = make_settings(litellm_base_url="https://team-proxy.example.com/v1")
    provider = make_provider(base_url="https://override.example.com/v1", settings=settings)

    assert str(provider.client.base_url).rstrip("/") == "https://override.example.com/v1"


async def test_call_chunk_returns_text_response():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.refusal = None
    fake_message.content = "line [0] looks fine."
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    result = await provider.call_chunk("prompt")

    assert result.analysis == "line [0] looks fine."


async def test_call_chunk_raises_request_error_on_empty_response():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.refusal = None
    fake_message.content = None
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("prompt")


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    request = httpx.Request("POST", "https://llm.etapinc.com/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    error = openai.RateLimitError("rate limited", response=response, body=None)
    provider.client.chat.completions.create = AsyncMock(side_effect=error)

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("prompt")
