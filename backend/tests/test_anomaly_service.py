from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.core.errors import BadRequestError, LLMQuotaExceededError, LLMRequestError
from app.schemas.analysis import AnalysisContext, ChatMessage, ChunkResult
from app.schemas.common import LogEvent
from app.services.anomaly_service import AnomalyService
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.litellm_provider import LiteLLMProvider
from app.services.llm.openai_provider import OpenAIProvider


def make_event(i: int, message: str) -> LogEvent:
    return LogEvent(
        source="cloudwatch",
        origin="test-group",
        stream_or_key="test-stream",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        message=message,
        line_index=i,
    )


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", gemini_rpm_limit=6000, **overrides)


async def test_analyze_returns_findings_from_single_chunk(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    async def fake_call_chunk(self, system, prompt):
        return ChunkResult(analysis="[0] something broke: ERROR boom")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    events = [make_event(0, "ERROR boom")]
    result = await service.analyze(
        events, AnalysisContext(source_description="test"), provider="gemini"
    )

    assert result.chunks_analyzed == 1
    assert result.analysis == "[0] something broke: ERROR boom"
    assert result.warnings == []
    assert result.model == settings.gemini_model


async def test_analyze_defaults_to_litellm_provider(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    called = {"count": 0}

    async def fake_call_chunk(self, system, prompt):
        called["count"] += 1
        return ChunkResult(analysis="")

    monkeypatch.setattr(LiteLLMProvider, "call_chunk", fake_call_chunk)

    events = [make_event(0, "ERROR boom")]
    result = await service.analyze(events, AnalysisContext(source_description="test"))

    assert called["count"] == 1
    assert result.model == settings.litellm_model


async def test_analyze_unknown_provider_raises_bad_request():
    settings = make_settings()
    service = AnomalyService(settings)
    events = [make_event(0, "ERROR boom")]

    with pytest.raises(BadRequestError):
        await service.analyze(
            events, AnalysisContext(source_description="test"), provider="bogus"
        )


async def test_analyze_with_user_prompt_reaches_llm_and_skips_prefilter(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    seen_prompts: list[str] = []

    async def fake_call_chunk(self, system, prompt):
        seen_prompts.append(prompt)
        return ChunkResult(analysis="")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    # plain lines the anomaly-scan regex prefilter would not select
    events = [make_event(i, f"user login ok id={i}") for i in range(3)]
    result = await service.analyze(
        events,
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="count successful logins",
    )

    assert "count successful logins" in seen_prompts[0]
    assert result.lines_considered == 3
    assert result.lines_skipped_by_prefilter == 0


async def test_analyze_includes_conversation_history_in_prompt(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    seen_prompts: list[str] = []

    async def fake_call_chunk(self, system, prompt):
        seen_prompts.append(prompt)
        return ChunkResult(analysis="")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    events = [make_event(0, "ERROR boom")]
    history = [
        ChatMessage(role="user", content="what happened first"),
        ChatMessage(role="assistant", content="a boom occurred at line 0"),
    ]
    await service.analyze(
        events,
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="what should we do next",
        history=history,
    )

    assert "what happened first" in seen_prompts[0]
    assert "a boom occurred at line 0" in seen_prompts[0]
    assert "what should we do next" in seen_prompts[0]


async def test_analyze_rejects_oversized_conversation_history():
    settings = make_settings(max_chat_history_messages=2)
    service = AnomalyService(settings)
    events = [make_event(0, "ERROR boom")]
    history = [ChatMessage(role="user", content=f"turn {i}") for i in range(3)]

    with pytest.raises(BadRequestError):
        await service.analyze(
            events,
            AnalysisContext(source_description="test"),
            provider="gemini",
            user_prompt="follow up",
            history=history,
        )


async def test_analyze_raises_quota_error_when_first_chunk_exhausted(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    async def raise_quota(*args, **kwargs):
        raise LLMQuotaExceededError("quota exceeded")

    monkeypatch.setattr(service, "_call_chunk", raise_quota)

    events = [make_event(0, "ERROR boom")]

    with pytest.raises(LLMQuotaExceededError):
        await service.analyze(events, AnalysisContext(source_description="test"))


async def test_analyze_returns_partial_findings_when_quota_hits_mid_run(monkeypatch):
    settings = make_settings(chunk_size_lines=1, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    call_count = {"n": 0}

    async def flaky_call(chunk_events, context, provider, max_retries, user_prompt=None, history=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return ChunkResult(analysis="[0] warning: x")
        raise LLMQuotaExceededError("quota exceeded")

    monkeypatch.setattr(service, "_call_chunk", flaky_call)

    events = [make_event(i, "ERROR boom") for i in range(3)]
    result = await service.analyze(events, AnalysisContext(source_description="test"))

    assert result.chunks_analyzed == 1
    assert result.analysis == "[0] warning: x"
    assert result.lines_analyzed == 1
    assert result.lines_not_analyzed == 2
    assert result.warnings


async def test_connection_reports_success(monkeypatch):
    settings = make_settings()
    service = AnomalyService(settings)

    async def fake_call_chunk(self, system, prompt):
        return ChunkResult(analysis="")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    result = await service.test_connection(provider="gemini")

    assert result.success is True
    assert result.model == settings.gemini_model


async def test_connection_reports_failure_from_provider_call(monkeypatch):
    settings = make_settings()
    service = AnomalyService(settings)

    async def fake_call_chunk(self, system, prompt):
        raise LLMRequestError("upstream said no")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    result = await service.test_connection(provider="gemini")

    assert result.success is False
    assert "upstream said no" in result.message


async def test_connection_reports_failure_when_required_api_key_missing():
    settings = make_settings()
    service = AnomalyService(settings)

    result = await service.test_connection(provider="openai", api_key=None)

    assert result.success is False
    assert "api_key" in result.message


async def test_connection_does_not_raise_for_unreachable_base_url(monkeypatch):
    settings = make_settings()
    service = AnomalyService(settings)

    async def fake_call_chunk(self, system, prompt):
        raise LLMRequestError("Connection refused")

    monkeypatch.setattr(OpenAIProvider, "call_chunk", fake_call_chunk)

    result = await service.test_connection(
        provider="openai", api_key="test-key", base_url="http://localhost:1/v1"
    )

    assert result.success is False
    assert "Connection refused" in result.message


@pytest.mark.parametrize("caps", [
    {"max_analysis_lines": 3},
    {"max_analysis_chars": 30},
    {"chunk_size_lines": 2, "gemini_max_chunks_per_analysis": 1},
])
async def test_coverage_accounts_for_limits(monkeypatch, caps):
    service = AnomalyService(make_settings(**caps))
    received = []

    async def respond(chunk_events, *args):
        received.extend(chunk_events)
        return ChunkResult(analysis="Errors occurred.")

    monkeypatch.setattr(service, "_call_chunk", respond)
    result = await service.analyze(
        [make_event(i, "ERROR boom") for i in range(8)],
        AnalysisContext(source_description="test"),
    )
    assert result.lines_submitted == 8
    assert result.lines_analyzed == len(received)
    assert result.lines_considered == len(received)
    assert result.lines_omitted_by_limits == 8 - len(received)
    assert result.lines_not_analyzed == 0
    assert result.warnings


async def test_coverage_accounts_for_failed_chunks_and_shortened_lines(monkeypatch):
    service = AnomalyService(make_settings(chunk_size_lines=1, max_line_length=20))

    async def respond(chunk_events, *args):
        if chunk_events[0].line_index == 1:
            raise LLMRequestError("unavailable")
        return ChunkResult(analysis="Errors occurred.")

    monkeypatch.setattr(service, "_call_chunk", respond)
    result = await service.analyze(
        [make_event(i, "ERROR " + "x" * 50) for i in range(2)],
        AnalysisContext(source_description="test"),
    )
    assert result.lines_submitted == 2
    assert result.lines_analyzed == 1
    assert result.lines_not_analyzed == 1
    assert result.lines_shortened == 2
    assert result.lines_omitted_by_limits == 0


@pytest.mark.parametrize("mode", ["empty", "filtered", "sampled", "custom"])
async def test_coverage_totals_reconcile(monkeypatch, mode):
    service = AnomalyService(make_settings(max_analysis_lines=5))
    events = [make_event(i, "normal operation") for i in range(10)]
    if mode == "empty":
        events = []
    elif mode == "filtered":
        events[5] = make_event(5, "ERROR boom")

    async def respond(*args):
        return ChunkResult(analysis="Reviewed logs.")

    monkeypatch.setattr(service, "_call_chunk", respond)
    result = await service.analyze(
        events, AnalysisContext(source_description="test"),
        user_prompt="Review normal operation" if mode == "custom" else None,
    )
    assert result.lines_submitted == len(events)
    assert result.lines_submitted == (
        result.lines_skipped_by_prefilter + result.lines_omitted_by_limits
        + result.lines_analyzed + result.lines_not_analyzed
    )
    assert result.lines_considered == result.lines_analyzed + result.lines_not_analyzed
    assert result.lines_shortened == 0
    if mode in ("filtered", "sampled"):
        assert result.lines_skipped_by_prefilter == 5
    elif mode == "custom":
        assert result.lines_skipped_by_prefilter == 0
        assert result.lines_omitted_by_limits == 5
