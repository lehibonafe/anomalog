from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.core.errors import BadRequestError, LLMQuotaExceededError, LLMRequestError
from app.schemas.analysis import AnalysisContext, ChunkResult, Finding
from app.schemas.common import LogEvent
from app.services.anomaly_service import AnomalyService
from app.services.llm.gemini_provider import GeminiProvider
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
    return Settings(gemini_api_key="test-key", gemini_rpm_limit=6000, **overrides)


async def test_analyze_returns_findings_from_single_chunk(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    async def fake_call_chunk(self, prompt):
        return ChunkResult(
            findings=[
                Finding(
                    id="f1",
                    severity="critical",
                    category="error",
                    line_index_start=0,
                    line_index_end=0,
                    excerpt="ERROR boom",
                    explanation="something broke",
                )
            ]
        )

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    events = [make_event(0, "ERROR boom")]
    result = await service.analyze(events, AnalysisContext(source_description="test"))

    assert result.chunks_analyzed == 1
    assert len(result.findings) == 1
    assert result.findings[0].id == "f1"
    assert result.warnings == []
    assert result.model == settings.gemini_model


async def test_analyze_defaults_to_gemini_provider(monkeypatch):
    settings = make_settings(chunk_size_lines=10, gemini_max_chunks_per_analysis=5)
    service = AnomalyService(settings)

    called = {"count": 0}

    async def fake_call_chunk(self, prompt):
        called["count"] += 1
        return ChunkResult(findings=[])

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    events = [make_event(0, "ERROR boom")]
    result = await service.analyze(events, AnalysisContext(source_description="test"))

    assert called["count"] == 1
    assert result.model == settings.gemini_model


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

    async def fake_call_chunk(self, prompt):
        seen_prompts.append(prompt)
        return ChunkResult(findings=[])

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    # plain lines the anomaly-scan regex prefilter would not select
    events = [make_event(i, f"user login ok id={i}") for i in range(3)]
    result = await service.analyze(
        events,
        AnalysisContext(source_description="test"),
        user_prompt="count successful logins",
    )

    assert "count successful logins" in seen_prompts[0]
    assert result.lines_considered == 3
    assert result.lines_skipped_by_prefilter == 0


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

    async def flaky_call(chunk_events, context, provider, max_retries, user_prompt=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return ChunkResult(
                findings=[
                    Finding(
                        id="f1",
                        severity="warning",
                        category="error",
                        line_index_start=0,
                        line_index_end=0,
                        excerpt="x",
                        explanation="y",
                    )
                ]
            )
        raise LLMQuotaExceededError("quota exceeded")

    monkeypatch.setattr(service, "_call_chunk", flaky_call)

    events = [make_event(i, "ERROR boom") for i in range(3)]
    result = await service.analyze(events, AnalysisContext(source_description="test"))

    assert result.chunks_analyzed == 1
    assert len(result.findings) == 1
    assert result.warnings


async def test_connection_reports_success(monkeypatch):
    settings = make_settings()
    service = AnomalyService(settings)

    async def fake_call_chunk(self, prompt):
        return ChunkResult(findings=[])

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    result = await service.test_connection(provider="gemini")

    assert result.success is True
    assert result.model == settings.gemini_model


async def test_connection_reports_failure_from_provider_call(monkeypatch):
    settings = make_settings()
    service = AnomalyService(settings)

    async def fake_call_chunk(self, prompt):
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

    async def fake_call_chunk(self, prompt):
        raise LLMRequestError("Connection refused")

    monkeypatch.setattr(OpenAIProvider, "call_chunk", fake_call_chunk)

    result = await service.test_connection(
        provider="openai", api_key="test-key", base_url="http://localhost:1/v1"
    )

    assert result.success is False
    assert "Connection refused" in result.message
