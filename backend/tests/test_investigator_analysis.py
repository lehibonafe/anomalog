from datetime import datetime, timezone

from app.config import Settings
from app.core.errors import LLMRequestError
from app.schemas.analysis import AnalysisContext, ChunkResult
from app.schemas.common import LogEvent
from app.services.anomaly_service import AnomalyService
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.prompt_v6 import REDUCTION_SYSTEM_PROMPT


def make_event(index: int) -> LogEvent:
    return LogEvent(
        source="cloudwatch",
        origin="test-group",
        stream_or_key="test-stream",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        message=f"status=500 service=checkout failure={index}",
        line_index=index,
    )


def make_settings() -> Settings:
    return Settings(
        gemini_api_key="test-key",
        litellm_api_key="test-litellm-key",
        gemini_rpm_limit=6000,
        gemini_max_retries=0,
        chunk_size_lines=1,
        gemini_max_chunks_per_analysis=5,
    )


async def test_multiple_batches_are_consolidated_for_the_operator_question(monkeypatch):
    service = AnomalyService(make_settings())
    responses = iter(
        [
            "Checkout has one 5xx in this batch [0].",
            "Checkout has one 5xx in this batch [1].",
            "Checkout has the most 5xx responses: 2 in the supplied sample [0-1].",
        ]
    )
    calls: list[tuple[str, str]] = []

    async def fake_call_chunk(self, system, prompt):
        calls.append((system, prompt))
        return ChunkResult(analysis=next(responses))

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    result = await service.analyze(
        [make_event(0), make_event(1)],
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="Which service has the most 5xx errors?",
    )

    assert result.analysis == (
        "Checkout has the most 5xx responses: 2 in the supplied sample [0-1]."
    )
    assert result.chunks_analyzed == 2
    assert result.chunks_total == 2
    assert len(calls) == 3
    assert calls[-1][0] == REDUCTION_SYSTEM_PROMPT
    assert "Which service has the most 5xx errors?" in calls[-1][1]
    assert "Checkout has one 5xx" in calls[-1][1]
    assert '"service_5xx":{"checkout":2}' in calls[0][1]


async def test_reduction_failure_returns_all_batch_answers(monkeypatch):
    service = AnomalyService(make_settings())
    calls = 0

    async def fake_call_chunk(self, system, prompt):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ChunkResult(analysis="Role A stopped an instance [0].")
        if calls == 2:
            return ChunkResult(analysis="Role B stopped another instance [1].")
        raise LLMRequestError("reducer unavailable")

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    result = await service.analyze(
        [make_event(0), make_event(1)],
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="Who stopped the EC2 instances?",
    )

    assert result.analysis == (
        "Role A stopped an instance [0].\n\nRole B stopped another instance [1]."
    )
    assert any("Could not consolidate" in warning for warning in result.warnings)


async def test_single_batch_answer_is_not_truncated(monkeypatch):
    service = AnomalyService(make_settings())

    async def fake_call_chunk(self, system, prompt):
        return ChunkResult(
            analysis=(
                "The instance was stopped by assumed role DeployRole [0]. "
                "The logs do not identify the human behind that role session."
            )
        )

    monkeypatch.setattr(GeminiProvider, "call_chunk", fake_call_chunk)

    result = await service.analyze(
        [make_event(0)],
        AnalysisContext(source_description="test"),
        provider="gemini",
        user_prompt="Who stopped the instance?",
    )

    assert result.analysis == (
        "The instance was stopped by assumed role DeployRole [0]. "
        "The logs do not identify the human behind that role session."
    )
