import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from app.config import Settings
from app.core.errors import LLMRequestError
from app.services.llm.base import LLMRateLimited
from app.services.llm.ollama_provider import DEFAULT_BASE_URL, OllamaProvider


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


def make_provider(api_key: str | None = None, base_url: str | None = None) -> OllamaProvider:
    settings = make_settings()
    return OllamaProvider(api_key=api_key, model="llama3.1", base_url=base_url, settings=settings)


def test_defaults_base_url_and_key_when_omitted():
    provider = make_provider(api_key=None, base_url=None)

    assert str(provider.client.base_url).rstrip("/") == DEFAULT_BASE_URL.rstrip("/")


async def test_call_chunk_parses_json_object_response():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.content = json.dumps({"findings": []})
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    result = await provider.call_chunk("prompt")

    assert result.findings == []


async def test_call_chunk_raises_request_error_on_malformed_json():
    provider = make_provider()
    fake_message = MagicMock()
    fake_message.content = "not json"
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=fake_message)]
    provider.client.chat.completions.create = AsyncMock(return_value=fake_completion)

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("prompt")


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    error = openai.RateLimitError("rate limited", response=response, body=None)
    provider.client.chat.completions.create = AsyncMock(side_effect=error)

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("prompt")
