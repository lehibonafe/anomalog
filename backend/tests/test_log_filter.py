from datetime import datetime, timezone

import pytest

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
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", **overrides)


def test_select_relevant_keeps_matches_and_context():
    events = [make_event(i, f"line {i}") for i in range(10)]
    events[5] = make_event(5, "ERROR something broke")
    settings = make_settings()

    kept, skipped = log_filter.select_relevant(events, settings)

    kept_indices = {e.line_index for e in kept}
    assert kept_indices == {3, 4, 5, 6, 7}
    assert skipped == 5


@pytest.mark.parametrize("status_code", [401, 403, 408, 429, 500, 502, 503, 504, 599])
def test_select_relevant_keeps_significant_http_statuses(status_code):
    events = [make_event(i, f"request completed with 200 at line {i}") for i in range(10)]
    events[5] = make_event(5, f"request completed with {status_code}")

    kept, skipped = log_filter.select_relevant(events, make_settings())

    assert [event.line_index for event in kept] == [3, 4, 5, 6, 7]
    assert skipped == 5


@pytest.mark.parametrize("status_code", [100, 200, 201, 301, 302, 400, 404, 409])
def test_select_relevant_does_not_treat_routine_http_statuses_as_significant(status_code):
    events = [make_event(i, f"request completed at line {i}") for i in range(15)]
    events[1] = make_event(1, f"request completed with {status_code}")
    events[10] = make_event(10, "ERROR request failed")

    kept, skipped = log_filter.select_relevant(events, make_settings())

    assert [event.line_index for event in kept] == [8, 9, 10, 11, 12]
    assert skipped == 10


def test_select_relevant_falls_back_to_sampling_when_no_matches():
    events = [make_event(i, f"line {i}") for i in range(100)]
    settings = make_settings(max_analysis_lines=10)

    kept, skipped = log_filter.select_relevant(events, settings)

    assert len(kept) <= 10
    assert skipped == 100 - len(kept)


def test_select_for_question_keeps_matches_and_context():
    events = [make_event(i, f"routine operation {i}") for i in range(12)]
    events[7] = make_event(7, "user login succeeded for account test")

    kept, skipped = log_filter.select_for_question(
        events, "count successful logins", make_settings()
    )

    assert [event.line_index for event in kept] == [5, 6, 7, 8, 9]
    assert skipped == 7


def test_select_for_question_understands_http_status_families():
    events = [make_event(i, "request status=200") for i in range(8)]
    events[4] = make_event(4, "request status=503 service=checkout")

    kept, _ = log_filter.select_for_question(
        events, "Which service has the most 5xx errors?", make_settings()
    )

    assert 4 in {event.line_index for event in kept}


def test_select_for_question_preserves_explicit_full_dataset_requests():
    events = [make_event(i, f"routine operation {i}") for i in range(20)]

    kept, skipped = log_filter.select_for_question(
        events, "How many logs are there in total?", make_settings()
    )

    assert kept == events
    assert skipped == 0


def test_compact_json_removes_whitespace_without_dropping_fields():
    event = make_event(0, '{ "status": 500, "service": "checkout" }')

    compacted = log_filter.compact_json([event])

    assert compacted[0].message == '{"service":"checkout","status":500}'


def test_derived_counts_combines_structured_and_plain_log_facets():
    events = [
        make_event(0, '{"service":"checkout","status":503}'),
        make_event(1, "service=checkout status_code=500 request failed"),
        make_event(2, "service=identity status=200 request complete"),
    ]

    counts = log_filter.derived_counts(events)

    assert counts["http_status"] == {"200": 1, "500": 1, "503": 1}
    assert counts["service"] == {"checkout": 2, "identity": 1}
    assert counts["service_5xx"] == {"checkout": 2}


def test_compress_duplicates_retains_representative_and_source_count():
    events = [
        make_event(i, f"ERROR request_id=12345678{i} database timeout")
        for i in range(5)
    ]

    result = log_filter.compress_duplicates(events)

    assert len(result.events) == 1
    assert result.collapsed == 4
    assert result.source_counts[result.events[0].line_index] == 5
    assert result.events[0].occurrence_count == 5


def test_compress_duplicates_handles_json_request_ids_conservatively():
    events = log_filter.compact_json([
        make_event(0, '{"request_id":"aaaaaaaa","service":"api","status":500}'),
        make_event(1, '{"request_id":"bbbbbbbb","service":"api","status":500}'),
    ])

    result = log_filter.compress_duplicates(events)

    assert result.collapsed == 1
    assert result.events[0].occurrence_count == 2


def test_compress_duplicates_does_not_hide_distinct_numeric_identities():
    events = [
        make_event(0, "actor account=123456789012 stopped instance"),
        make_event(1, "actor account=210987654321 stopped instance"),
    ]

    result = log_filter.compress_duplicates(events)

    assert result.collapsed == 0
    assert len(result.events) == 2


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


def test_truncate_and_cap_enforces_token_budget():
    events = [make_event(i, f"ERROR unique={i} " + "x" * 1000) for i in range(10)]
    settings = make_settings(max_analysis_tokens=1000, max_analysis_chars=20000)

    capped = log_filter.truncate_and_cap(events, settings)

    assert 0 < len(capped) < len(events)
    assert sum(log_filter.estimate_event_tokens(event) for event in capped) <= 1000


def test_chunk_splits_and_caps_chunk_count():
    events = [make_event(i, "line") for i in range(1000)]
    settings = make_settings(chunk_size_lines=100, gemini_max_chunks_per_analysis=3)

    chunks = log_filter.chunk(events, settings)

    assert len(chunks) == 3
    assert all(len(c) == 100 for c in chunks)
