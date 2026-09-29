from datetime import datetime, timezone

from app.schemas.analysis import AnalysisContext
from app.schemas.common import LogEvent
from app.services import log_filter
from app.services.llm.prompt_v6 import (
    PROMPT_VERSION,
    REDUCTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_prompt,
    build_reduction_prompt,
)


def test_prompt_v6_is_question_driven_and_evidence_grounded():
    assert PROMPT_VERSION == "log_analysis/v6"
    assert "answer that question first" in SYSTEM_PROMPT
    assert "userIdentity ARN" in SYSTEM_PROMPT
    assert "ranking and counting questions" in SYSTEM_PROMPT
    assert "exact log-line citations" in SYSTEM_PROMPT


def test_reduction_prompt_preserves_question_and_requires_combined_counts():
    prompt = build_reduction_prompt(
        ["api has 2 errors [1-2]", "api has 3 errors [8-10]"],
        "Which service has the most errors?",
    )

    assert "Which service has the most errors?" in prompt
    assert "api has 2 errors" in prompt
    assert "add counts for the same entity" in REDUCTION_SYSTEM_PROMPT


def test_prompt_marks_backend_aggregates_as_trusted_metadata():
    events = [
        LogEvent(
            source="cloudwatch",
            origin="group",
            stream_or_key="stream",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            message=f"ERROR request_id=12345678{i} timeout",
            line_index=i,
        )
        for i in range(3)
    ]
    compressed = log_filter.compress_duplicates(events)

    prompt = build_prompt(
        compressed.events, AnalysisContext(source_description="test")
    )

    assert "app_occurrences=3" in prompt
    assert "trusted," in SYSTEM_PROMPT
    assert "deterministic metadata" in SYSTEM_PROMPT
