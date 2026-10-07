from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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


def test_model_allowlist_loads_from_environment(monkeypatch):
    monkeypatch.setenv(
        "MODEL_BASE_URL_ALLOWLIST", '{"ollama":["http://ollama:11434/v1"]}'
    )
    settings = Settings(litellm_api_key="test", _env_file=None)
    assert settings.model_base_url_allowlist == {
        "ollama": ["http://ollama:11434/v1"]
    }


def test_model_allowlist_rejects_url_with_embedded_credentials():
    with pytest.raises(ValidationError, match="without credentials"):
        make_settings(
            model_base_url_allowlist={"litellm": ["https://key@proxy.example/v1"]}
        )


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
    assert "app_visible_logs=3" in seen_prompts[0]
    assert result.lines_considered == 3
    assert result.lines_skipped_by_prefilter == 0


async def test_custom_question_uses_question_aware_retrieval(monkeypatch):
    settings = make_settings(chunk_size_lines=50, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)
    seen_prompts: list[str] = []

    async def fake_call_chunk(self, system, prompt):
        seen_prompts.append(prompt)
        return ChunkResult(analysis="Account test logged in [50].")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)
    events = [make_event(i, f"routine heartbeat sequence={i}") for i in range(100)]
    events[50] = make_event(50, "user login succeeded account=test")

    result = await service.analyze(
        events,
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="Which account logged in successfully?",
    )

    assert result.lines_analyzed == 5
    assert result.lines_skipped_by_prefilter == 95
    assert "[50]" in seen_prompts[0]
    assert "sequence=0" not in seen_prompts[0]


async def test_duplicate_compression_reports_source_coverage(monkeypatch):
    service = AnomalyService(make_settings())
    received: list[LogEvent] = []

    async def respond(chunk_events, *args):
        received.extend(chunk_events)
        return ChunkResult(analysis="Database timed out 10 times [0].")

    monkeypatch.setattr(service, "_call_chunk", respond)
    events = [
        make_event(i, f"ERROR request_id=12345678{i} database timeout")
        for i in range(10)
    ]

    result = await service.analyze(events, AnalysisContext(source_description="test"))

    assert len(received) == 1
    assert result.lines_analyzed == 10
    assert result.lines_sent_to_model == 1
    assert result.lines_collapsed_as_duplicates == 9
    assert result.lines_omitted_by_limits == 0
    assert result.estimated_input_tokens > 0


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


async def test_analyze_trims_history_to_token_budget(monkeypatch):
    settings = make_settings(max_chat_history_tokens=100)
    service = AnomalyService(settings)

    async def fake_call_chunk(self, system, prompt):
        return ChunkResult(analysis="Reviewed logs.")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)
    history = [
        ChatMessage(role="user", content="old context " * 100),
        ChatMessage(role="assistant", content="recent finding " * 100),
    ]
    result = await service.analyze(
        [make_event(0, "ERROR boom")],
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="what happened?",
        history=history,
    )

    assert result.history_messages_omitted == 1
    assert any("Conversation history was compacted" in warning for warning in result.warnings)


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

    events = [make_event(i, f"ERROR boom code={i}") for i in range(3)]
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
    settings = make_settings(
        model_base_url_allowlist={"openai": ["http://localhost:1/v1"]}
    )
    service = AnomalyService(settings)

    async def fake_call_chunk(self, system, prompt):
        raise LLMRequestError("Connection refused")

    monkeypatch.setattr(OpenAIProvider, "call_chunk", fake_call_chunk)

    result = await service.test_connection(
        provider="openai", api_key="test-key", base_url="http://localhost:1/v1"
    )

    assert result.success is False
    assert "Connection refused" in result.message


async def test_analyze_rejects_unapproved_litellm_destination_before_model_call(monkeypatch):
    service = AnomalyService(make_settings())
    called = False

    async def fake_call_chunk(*args, **kwargs):
        nonlocal called
        called = True
        return ChunkResult(analysis="unexpected")

    monkeypatch.setattr(LiteLLMProvider, "call_chunk", fake_call_chunk)
    with pytest.raises(BadRequestError, match="not approved"):
        await service.analyze(
            [make_event(0, "ERROR boom")],
            AnalysisContext(source_description="test"),
            base_url="http://127.0.0.1:1234/v1",
        )
    assert called is False


async def test_connection_rejects_unapproved_destination_before_model_call(monkeypatch):
    service = AnomalyService(make_settings())
    called = False

    async def fake_call_chunk(*args, **kwargs):
        nonlocal called
        called = True
        return ChunkResult(analysis="unexpected")

    monkeypatch.setattr(OpenAIProvider, "call_chunk", fake_call_chunk)
    result = await service.test_connection(
        provider="openai", api_key="client-key", base_url="http://127.0.0.1:1234/v1"
    )
    assert result.success is False
    assert "not approved" in result.message
    assert called is False


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
        [make_event(i, f"ERROR boom code={i}") for i in range(8)],
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
        [make_event(i, f"ERROR code={i} " + "x" * 50) for i in range(2)],
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
    events = [make_event(i, f"normal operation code={i}") for i in range(10)]
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
