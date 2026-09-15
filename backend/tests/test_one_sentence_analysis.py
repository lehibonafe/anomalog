from datetime import datetime, timezone

from app.config import Settings
from app.core.errors import LLMRequestError
from app.schemas.analysis import AnalysisContext, ChunkResult
from app.schemas.common import LogEvent
from app.services.anomaly_service import AnomalyService, _normalize_one_sentence
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.prompt_v5 import REDUCTION_SYSTEM_PROMPT


def make_event(index: int) -> LogEvent:
    return LogEvent(
        source='cloudwatch',
        origin='test-group',
        stream_or_key='test-stream',
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        message=f'ERROR failure {index}',
        line_index=index,
    )


def make_settings() -> Settings:
    return Settings(
        gemini_api_key='test-key',
        litellm_api_key='test-litellm-key',
        gemini_rpm_limit=6000,
        gemini_max_retries=0,
        chunk_size_lines=1,
        gemini_max_chunks_per_analysis=5,
    )


async def test_multiple_chunks_are_reduced_to_one_literal_sentence(monkeypatch):
    service = AnomalyService(make_settings())
    responses = iter(
        [
            'HIGH authentication failures affected checkout [0].',
            'CRITICAL payment processing stopped [1].',
            'CRITICAL payment processing stopped in the visible logs [1]. '
            'Restart the service.',
        ]
    )
    calls: list[tuple[str, str]] = []

    async def fake_call_chunk(self, system, prompt):
        calls.append((system, prompt))
        return ChunkResult(analysis=next(responses))

    monkeypatch.setattr(GeminiProvider, 'call_chunk', fake_call_chunk)

    result = await service.analyze(
        [make_event(0), make_event(1)],
        AnalysisContext(source_description='test'),
        provider='gemini',
    )

    assert result.analysis == (
        'CRITICAL payment processing stopped in the visible logs [1].'
    )
    assert result.chunks_analyzed == 2
    assert result.chunks_total == 2
    assert len(calls) == 3
    assert calls[-1][0] == REDUCTION_SYSTEM_PROMPT
    assert 'authentication failures' in calls[-1][1]
    assert '\n' not in result.analysis


async def test_reduction_failure_returns_strongest_chunk_sentence(monkeypatch):
    service = AnomalyService(make_settings())
    calls = 0

    async def fake_call_chunk(self, system, prompt):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ChunkResult(analysis='MEDIUM retries increased [0]. More detail.')
        if calls == 2:
            return ChunkResult(analysis='HIGH requests failed [1]. More detail.')
        raise LLMRequestError('reducer unavailable')

    monkeypatch.setattr(GeminiProvider, 'call_chunk', fake_call_chunk)

    result = await service.analyze(
        [make_event(0), make_event(1)],
        AnalysisContext(source_description='test'),
        provider='gemini',
    )

    assert result.analysis == 'HIGH requests failed [1].'
    assert result.chunks_analyzed == 2
    assert any('Could not consolidate' in warning for warning in result.warnings)


async def test_single_chunk_model_noncompliance_is_trimmed(monkeypatch):
    service = AnomalyService(make_settings())

    async def fake_call_chunk(self, system, prompt):
        return ChunkResult(
            analysis=(
                'Summary\nHIGH checkout failed [0].\n'
                'Recommended Next Steps\nRestart checkout.'
            )
        )

    monkeypatch.setattr(GeminiProvider, 'call_chunk', fake_call_chunk)

    result = await service.analyze(
        [make_event(0)],
        AnalysisContext(source_description='test'),
        provider='gemini',
    )

    assert result.analysis == 'HIGH checkout failed [0].'


def test_sentence_guard_preserves_decimal_ip_abbreviation_and_citation():
    text = (
        'Summary\nHIGH API 10.0.0.1 took 1.5 seconds, e.g. during checkout '
        '[4-7]. A second sentence must be removed.'
    )

    assert _normalize_one_sentence(text) == (
        'HIGH API 10.0.0.1 took 1.5 seconds, e.g. during checkout [4-7].'
    )
