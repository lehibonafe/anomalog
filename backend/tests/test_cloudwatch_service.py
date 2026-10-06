import base64
import json
import zlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.core.errors import BadRequestError
from app.services import cloudwatch_service


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", masking_service_api_key=None, **overrides)


@patch("app.services.cloudwatch_service.get_logs_client")
def test_list_log_groups_includes_linked_accounts_and_returns_identifiers(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    source_arn = "arn:aws:logs:ap-southeast-1:222222222222:log-group:/aws/lambda/shared:*"
    mock_client.describe_log_groups.return_value = {
        "logGroups": [
            {
                "logGroupName": "/aws/lambda/shared",
                "arn": source_arn,
                "creationTime": 1000,
            }
        ]
    }

    result = cloudwatch_service.list_log_groups(
        keyword="/aws/lambda",
        next_token=None,
        limit=50,
        settings=make_settings(aws_include_linked_accounts=True),
    )

    mock_client.describe_log_groups.assert_called_once_with(
        limit=50,
        includeLinkedAccounts=True,
        logGroupNamePattern="/aws/lambda",
    )
    assert result.log_groups[0].identifier == source_arn.removesuffix(":*")
    assert result.log_groups[0].account_id == "222222222222"


@patch("app.services.cloudwatch_service.get_logs_client")
def test_search_log_events_uses_identifier_for_cross_account_group(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.filter_log_events.return_value = {
        "events": [{"logStreamName": "stream", "timestamp": 1000, "message": "event"}]
    }
    identifier = "arn:aws:logs:ap-southeast-1:222222222222:log-group:/aws/lambda/shared"

    result = cloudwatch_service.search_log_events(
        log_group_names=[identifier],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        filter_pattern=None,
        limit=100,
        cursor=None,
        settings=make_settings(),
    )

    kwargs = mock_client.filter_log_events.call_args.kwargs
    assert kwargs["logGroupIdentifier"] == identifier
    assert "logGroupName" not in kwargs
    assert result.events[0].origin == "/aws/lambda/shared"


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


@patch("app.services.cloudwatch_service.get_logs_client")
def test_pagination_preserves_events_and_unvisited_groups(mock_get_client):
    data = {name: [f"{name}-{i}" for i in range(4)] for name in ("a", "b", "c")}

    def fetch(logGroupName, limit, nextToken="0", **kwargs):
        start = int(nextToken)
        messages = data[logGroupName][start:start + limit]
        response = {"events": [{"message": message, "timestamp": 1000} for message in messages]}
        if start + len(messages) < len(data[logGroupName]):
            response["nextToken"] = str(start + len(messages))
        return response

    mock_get_client.return_value.filter_log_events.side_effect = fetch
    cursor = None
    messages = []
    for _ in range(10):
        result = cloudwatch_service.search_log_events(
            ["a", "b", "c"], datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc), None, 3, cursor, make_settings(),
        )
        assert len(result.events) <= 3
        messages.extend(event.message for event in result.events)
        cursor = result.cursor
        if cursor is None:
            break
    assert cursor is None
    assert sorted(messages) == sorted(message for group in data.values() for message in group)


@patch("app.services.cloudwatch_service.get_logs_client")
def test_empty_page_preserves_continuation(mock_get_client):
    mock_get_client.return_value.filter_log_events.side_effect = [
        {"events": [], "nextToken": "continue"},
        {"events": [{"message": "later event", "timestamp": 1000}]},
    ]
    args = dict(
        log_group_names=["a"], start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc), filter_pattern=None,
        limit=1, settings=make_settings(),
    )
    first = cloudwatch_service.search_log_events(**args, cursor=None)
    assert first.events == []
    assert first.cursor is not None
    second = cloudwatch_service.search_log_events(**args, cursor=first.cursor)
    assert [event.message for event in second.events] == ["later event"]
    assert second.cursor is None


@patch("app.services.cloudwatch_service.get_logs_client")
def test_interleaved_groups_stay_ordered_across_pages(mock_get_client):
    data = {
        "a": [(1000, "a-first"), (3000, "a-last")],
        "b": [(2000, "b-middle")],
    }

    def fetch(logGroupName, limit, nextToken="0", **kwargs):
        start = int(nextToken)
        page = data[logGroupName][start:start + limit]
        response = {
            "events": [{"timestamp": stamp, "message": message} for stamp, message in page]
        }
        if start + len(page) < len(data[logGroupName]):
            response["nextToken"] = str(start + len(page))
        return response

    mock_get_client.return_value.filter_log_events.side_effect = fetch
    args = dict(
        log_group_names=["a", "b"],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        filter_pattern=None,
        limit=2,
        settings=make_settings(),
    )
    first = cloudwatch_service.search_log_events(**args, cursor=None)
    second = cloudwatch_service.search_log_events(**args, cursor=first.cursor)

    assert [event.message for event in first.events + second.events] == [
        "a-first", "b-middle", "a-last"
    ]
    assert second.cursor is None


@patch("app.services.cloudwatch_service.get_logs_client")
def test_invalid_cursor_returns_client_error(mock_get_client):
    with pytest.raises(BadRequestError, match="Invalid or expired search cursor"):
        cloudwatch_service.search_log_events(
            ["a"], datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc), None, 2,
            "not-a-valid-cursor", make_settings(),
        )
    mock_get_client.return_value.filter_log_events.assert_not_called()


@patch("app.services.cloudwatch_service.get_logs_client")
def test_cursor_cannot_be_reused_with_another_filter(mock_get_client):
    mock_get_client.return_value.filter_log_events.return_value = {
        "events": [{"timestamp": 1000, "message": "one"}],
        "nextToken": "next",
    }
    args = dict(
        log_group_names=["a"], start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc), limit=1,
        settings=make_settings(),
    )
    first = cloudwatch_service.search_log_events(**args, filter_pattern=None, cursor=None)
    with pytest.raises(BadRequestError, match="Invalid or expired search cursor"):
        cloudwatch_service.search_log_events(**args, filter_pattern="ERROR", cursor=first.cursor)


@patch("app.services.cloudwatch_service.get_logs_client")
def test_buffered_cursor_events_are_masked_again_before_delivery(mock_get_client):
    data = {
        "a": [(1000, "first"), (3000, "jane.doe@example.com")],
        "b": [(2000, "middle")],
    }

    def fetch(logGroupName, limit, nextToken="0", **kwargs):
        start = int(nextToken)
        page = data[logGroupName][start:start + limit]
        return {"events": [
            {"timestamp": stamp, "message": message} for stamp, message in page
        ]}

    mock_get_client.return_value.filter_log_events.side_effect = fetch
    args = dict(
        log_group_names=["a", "b"],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        filter_pattern=None, limit=2, settings=make_settings(),
    )
    first = cloudwatch_service.search_log_events(**args, cursor=None)
    payload = json.loads(zlib.decompress(base64.urlsafe_b64decode(first.cursor)))
    assert "jane.doe@example.com" not in json.dumps(payload)

    # Even a client-edited cursor cannot bypass the masking step.
    payload["groups"][0]["pending"][0]["message"] = "jane.doe@example.com"
    altered = base64.urlsafe_b64encode(zlib.compress(json.dumps(payload).encode())).decode()
    second = cloudwatch_service.search_log_events(**args, cursor=altered)
    assert "jane.doe@example.com" not in second.events[0].message
    assert "***MASKED***" in second.events[0].message
