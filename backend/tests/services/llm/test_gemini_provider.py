from unittest.mock import AsyncMock, MagicMock

import pytest
from google import genai

from app.config import Settings
from app.core.errors import LLMRequestError
from app.services.llm.base import LLMRateLimited
from app.services.llm.gemini_provider import GeminiProvider


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", **overrides)


def make_provider() -> GeminiProvider:
    settings = make_settings()
    return GeminiProvider(api_key=None, model=settings.gemini_model, base_url=None, settings=settings)


def test_recommended_default_model():
    defaults = GeminiProvider.resolve_defaults(make_settings())

    assert defaults.model == "gemini-3.8-flash"


async def test_call_chunk_returns_text_response():
    provider = make_provider()
    fake_response = MagicMock()
    fake_response.text = "line [0] looks fine."
    provider.client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    result = await provider.call_chunk("system prompt", "prompt")

    assert result.analysis == "line [0] looks fine."
    config = provider.client.aio.models.generate_content.await_args.kwargs["config"]
    assert config.temperature is None
    assert config.thinking_config.thinking_level.value == "LOW"
    assert config.max_output_tokens == 2048


async def test_gemini_25_override_uses_legacy_thinking_budget():
    settings = make_settings(gemini_thinking_budget=0)
    provider = GeminiProvider(
        api_key=None, model="gemini-2.5-flash", base_url=None, settings=settings
    )
    provider.client.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(text="line [0] looks fine.")
    )

    await provider.call_chunk("system prompt", "prompt")

    config = provider.client.aio.models.generate_content.await_args.kwargs["config"]
    assert config.temperature == 0.1
    assert config.thinking_config.thinking_budget == 0


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    error = genai.errors.ClientError(429, {"error": {"message": "quota exceeded"}})
    provider.client.aio.models.generate_content = AsyncMock(side_effect=error)

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("system prompt", "prompt")


async def test_call_chunk_raises_request_error_on_other_failure():
    provider = make_provider()
    provider.client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("system prompt", "prompt")
