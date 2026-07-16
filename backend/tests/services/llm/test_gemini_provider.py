from unittest.mock import AsyncMock, MagicMock

import pytest
from google import genai

from app.config import Settings
from app.core.errors import LLMRequestError
from app.services.llm.base import LLMRateLimited
from app.services.llm.gemini_provider import GeminiProvider


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


def make_provider() -> GeminiProvider:
    settings = make_settings()
    return GeminiProvider(api_key=None, model="gemini-2.5-flash", base_url=None, settings=settings)


async def test_call_chunk_returns_text_response():
    provider = make_provider()
    fake_response = MagicMock()
    fake_response.text = "line [0] looks fine."
    provider.client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    result = await provider.call_chunk("prompt")

    assert result.analysis == "line [0] looks fine."


async def test_call_chunk_raises_rate_limited_on_429():
    provider = make_provider()
    error = genai.errors.ClientError(429, {"error": {"message": "quota exceeded"}})
    provider.client.aio.models.generate_content = AsyncMock(side_effect=error)

    with pytest.raises(LLMRateLimited):
        await provider.call_chunk("prompt")


async def test_call_chunk_raises_request_error_on_other_failure():
    provider = make_provider()
    provider.client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(LLMRequestError):
        await provider.call_chunk("prompt")
