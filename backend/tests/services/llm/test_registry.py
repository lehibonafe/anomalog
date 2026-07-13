import pytest

from app.core.errors import BadRequestError
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.registry import get_provider_class


def test_get_provider_class_resolves_all_known_providers():
    assert get_provider_class("gemini") is GeminiProvider
    assert get_provider_class("openai") is OpenAIProvider
    assert get_provider_class("anthropic") is AnthropicProvider
    assert get_provider_class("ollama") is OllamaProvider


def test_get_provider_class_raises_on_unknown_provider():
    with pytest.raises(BadRequestError):
        get_provider_class("bogus")
