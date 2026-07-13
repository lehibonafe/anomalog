from datetime import datetime, timezone

from app.config import Settings
from app.schemas.common import LogEvent
from app.services import log_filter


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
    return Settings(gemini_api_key="test-key", **overrides)


def test_select_relevant_keeps_matches_and_context():
    events = [make_event(i, f"line {i}") for i in range(10)]
    events[5] = make_event(5, "ERROR something broke")
    settings = make_settings()

    kept, skipped = log_filter.select_relevant(events, settings)

    kept_indices = {e.line_index for e in kept}
    assert kept_indices == {3, 4, 5, 6, 7}
    assert skipped == 5


def test_select_relevant_falls_back_to_sampling_when_no_matches():
    events = [make_event(i, f"line {i}") for i in range(100)]
    settings = make_settings(max_analysis_lines=10)

    kept, skipped = log_filter.select_relevant(events, settings)

    assert len(kept) <= 10
    assert skipped == 100 - len(kept)


def test_truncate_and_cap_prefers_most_recent_lines():
    events = [make_event(i, "x" * 10) for i in range(20)]
    settings = make_settings(
        max_analysis_lines=5, max_analysis_chars=1000, max_line_length=100
    )

    capped = log_filter.truncate_and_cap(events, settings)

    assert [e.line_index for e in capped] == [15, 16, 17, 18, 19]


def test_truncate_and_cap_truncates_long_lines():
    events = [make_event(0, "x" * 500)]
    settings = make_settings(max_line_length=50)

    capped = log_filter.truncate_and_cap(events, settings)

    assert len(capped[0].message) <= 50 + len(" ... ")


def test_chunk_splits_and_caps_chunk_count():
    events = [make_event(i, "line") for i in range(1000)]
    settings = make_settings(chunk_size_lines=100, gemini_max_chunks_per_analysis=3)

    chunks = log_filter.chunk(events, settings)

    assert len(chunks) == 3
    assert all(len(c) == 100 for c in chunks)
