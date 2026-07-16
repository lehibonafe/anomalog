from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.core.errors import BadRequestError
from app.services import cloudwatch_service


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


@patch("app.services.cloudwatch_service.get_logs_client")
def test_search_log_events_rejects_range_over_max_days(mock_get_client):
    settings = make_settings(max_time_range_days=7)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=7, seconds=1)

    with pytest.raises(BadRequestError):
        cloudwatch_service.search_log_events(
            log_group_names=["group-a"],
            start_time=start,
            end_time=end,
            filter_pattern=None,
            limit=100,
            cursor=None,
            settings=settings,
        )

    mock_get_client.assert_not_called()


@patch("app.services.cloudwatch_service.get_logs_client")
def test_search_log_events_allows_range_at_exactly_max_days(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.filter_log_events.return_value = {"events": []}

    settings = make_settings(max_time_range_days=7)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=7)

    result = cloudwatch_service.search_log_events(
        log_group_names=["group-a"],
        start_time=start,
        end_time=end,
        filter_pattern=None,
        limit=100,
        cursor=None,
        settings=settings,
    )

    assert result.events == []


@patch("app.services.cloudwatch_service.get_logs_client")
def test_search_log_events_merges_and_sorts_across_groups(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    def filter_log_events(logGroupName, **kwargs):
        if logGroupName == "group-a":
            return {
                "events": [
                    {"logStreamName": "s1", "timestamp": 3000, "message": "a-late"},
                    {"logStreamName": "s1", "timestamp": 1000, "message": "a-early"},
                ]
            }
        return {
            "events": [
                {"logStreamName": "s2", "timestamp": 2000, "message": "b-mid"},
            ]
        }

    mock_client.filter_log_events.side_effect = filter_log_events

    settings = make_settings()
    result = cloudwatch_service.search_log_events(
        log_group_names=["group-a", "group-b"],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        filter_pattern=None,
        limit=100,
        cursor=None,
        settings=settings,
    )

    messages = [e.message for e in result.events]
    assert messages == ["a-early", "b-mid", "a-late"]
    assert [e.line_index for e in result.events] == [0, 1, 2]
    assert result.cursor is None


@patch("app.services.cloudwatch_service.get_logs_client")
def test_search_log_events_masks_sensitive_data(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.filter_log_events.return_value = {
        "events": [
            {
                "logStreamName": "s1",
                "timestamp": 1000,
                "message": "user login: jane.doe@example.com",
            },
        ]
    }

    settings = make_settings()
    result = cloudwatch_service.search_log_events(
        log_group_names=["group-a"],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        filter_pattern=None,
        limit=100,
        cursor=None,
        settings=settings,
    )

    assert "jane.doe@example.com" not in result.events[0].message
    assert "***MASKED***" in result.events[0].message


@patch("app.services.cloudwatch_service.get_logs_client")
def test_search_log_events_builds_cursor_when_more_pages_exist(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.filter_log_events.return_value = {
        "events": [{"logStreamName": "s1", "timestamp": 1000, "message": "x"}],
        "nextToken": "token-1",
    }

    settings = make_settings()
    result = cloudwatch_service.search_log_events(
        log_group_names=["group-a"],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        filter_pattern=None,
        limit=100,
        cursor=None,
        settings=settings,
    )

    assert result.cursor is not None
    decoded = cloudwatch_service._decode_cursor(result.cursor)
    assert decoded == {"group-a": "token-1"}
