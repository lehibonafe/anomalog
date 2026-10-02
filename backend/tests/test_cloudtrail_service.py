from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.core.errors import BadRequestError
from app.services import cloudtrail_service


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", masking_service_api_key=None, **overrides)


@patch("app.services.cloudtrail_service.get_cloudtrail_client")
def test_lookup_events_returns_masked_sorted_events(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.lookup_events.return_value = {
        "Events": [
            {
                "EventName": "ConsoleLogin",
                "EventTime": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                "CloudTrailEvent": '{"userIdentity": {"userName": "jane.doe@example.com"}}',
            },
            {
                "EventName": "DeleteBucket",
                "EventTime": datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                "CloudTrailEvent": '{"eventName": "DeleteBucket"}',
            },
        ]
    }

    settings = make_settings()
    result = cloudtrail_service.lookup_events(
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        lookup_attribute_key=None,
        lookup_attribute_value=None,
        limit=100,
        cursor=None,
        settings=settings,
    )

    assert [e.stream_or_key for e in result.events] == ["DeleteBucket", "ConsoleLogin"]
    assert "jane.doe@example.com" not in result.events[1].message
    assert "***MASKED***" in result.events[1].message
    assert [e.line_index for e in result.events] == [0, 1]
    assert result.cursor is None


@patch("app.services.cloudtrail_service.get_cloudtrail_client")
def test_lookup_events_passes_lookup_attribute(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.lookup_events.return_value = {"Events": []}

    settings = make_settings()
    cloudtrail_service.lookup_events(
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        lookup_attribute_key="EventName",
        lookup_attribute_value="ConsoleLogin",
        limit=100,
        cursor=None,
        settings=settings,
    )

    kwargs = mock_client.lookup_events.call_args.kwargs
    assert kwargs["LookupAttributes"] == [
        {"AttributeKey": "EventName", "AttributeValue": "ConsoleLogin"}
    ]


@patch("app.services.cloudtrail_service.get_cloudtrail_client")
@patch("app.services.cloudtrail_service.get_logs_client")
def test_search_events_reads_configured_centralized_groups(
    mock_get_logs_client,
    mock_get_cloudtrail_client,
):
    mock_client = MagicMock()
    mock_get_logs_client.return_value = mock_client
    group_arn = (
        "arn:aws:logs:ap-southeast-1:111111111111:"
        "log-group:/aws/cloudtrail/source-b:*"
    )

    def fetch(**kwargs):
        if kwargs.get("logGroupName") == "/aws/cloudtrail/source-a":
            return {
                "events": [
                    {
                        "timestamp": 1767268800000,
                        "message": (
                            '{"eventName":"ConsoleLogin",'
                            '"eventTime":"2026-01-01T12:00:00Z",'
                            '"recipientAccountId":"222222222222",'
                            '"awsRegion":"ap-southeast-1",'
                            '"userIdentity":{"userName":"jane.doe@example.com"}}'
                        ),
                    }
                ]
            }
        return {
            "events": [
                {
                    "timestamp": 1767261600000,
                    "message": (
                        '{"eventName":"ConsoleLogin",'
                        '"eventTime":"2026-01-01T10:00:00Z",'
                        '"recipientAccountId":"333333333333",'
                        '"awsRegion":"us-east-1"}'
                    ),
                }
            ]
        }

    mock_client.filter_log_events.side_effect = fetch
    settings = make_settings(
        cloudtrail_log_group_identifiers=f"/aws/cloudtrail/source-a, {group_arn}"
    )

    result = cloudtrail_service.search_events(
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        lookup_attribute_key="EventName",
        lookup_attribute_value="ConsoleLogin",
        limit=100,
        cursor=None,
        settings=settings,
    )

    mock_get_cloudtrail_client.assert_not_called()
    calls = mock_client.filter_log_events.call_args_list
    assert calls[0].kwargs["logGroupName"] == "/aws/cloudtrail/source-a"
    assert calls[1].kwargs["logGroupIdentifier"] == group_arn.removesuffix(":*")
    assert calls[0].kwargs["filterPattern"] == '{ ($.eventName = "ConsoleLogin") }'
    assert [event.origin for event in result.events] == [
        "cloudtrail:333333333333:us-east-1",
        "cloudtrail:222222222222:ap-southeast-1",
    ]
    assert all(event.source == "cloudtrail" for event in result.events)
    assert all(event.stream_or_key == "ConsoleLogin" for event in result.events)
    assert "jane.doe@example.com" not in result.events[1].message
    assert "***MASKED***" in result.events[1].message


@patch("app.services.cloudtrail_service.get_logs_client")
def test_centralized_search_preserves_multi_group_pagination(mock_get_client):
    data = {
        group: [
            {
                "timestamp": 1000,
                "message": f'{{"eventName":"{group}-{index}"}}',
            }
            for index in range(3)
        ]
        for group in ("group-a", "group-b")
    }

    def fetch(logGroupName, limit, nextToken="0", **kwargs):
        start = int(nextToken)
        events = data[logGroupName][start:start + limit]
        response = {"events": events}
        if start + len(events) < len(data[logGroupName]):
            response["nextToken"] = str(start + len(events))
        return response

    mock_get_client.return_value.filter_log_events.side_effect = fetch
    settings = make_settings(cloudtrail_log_group_identifiers="group-a,group-b")
    cursor = None
    event_names = []

    for _ in range(10):
        result = cloudtrail_service.search_events(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            None,
            None,
            2,
            cursor,
            settings,
        )
        assert len(result.events) <= 2
        event_names.extend(event.stream_or_key for event in result.events)
        cursor = result.cursor
        if cursor is None:
            break

    assert cursor is None
    assert sorted(event_names) == sorted(
        f"{group}-{index}" for group in data for index in range(3)
    )


def test_centralized_read_only_filter_uses_json_boolean():
    assert cloudtrail_service._filter_pattern("ReadOnly", "TRUE") == (
        "{ $.readOnly IS TRUE }"
    )


@patch("app.services.cloudtrail_service.get_cloudtrail_client")
def test_lookup_events_rejects_range_over_max_days(mock_get_client):
    settings = make_settings(max_time_range_days=7)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=7, seconds=1)

    with pytest.raises(BadRequestError):
        cloudtrail_service.lookup_events(
            start_time=start,
            end_time=end,
            lookup_attribute_key=None,
            lookup_attribute_value=None,
            limit=100,
            cursor=None,
            settings=settings,
        )

    mock_get_client.assert_not_called()


@pytest.mark.parametrize("limit", [1, 17, 75])
@patch("app.services.cloudtrail_service.get_cloudtrail_client")
def test_pagination_preserves_every_event(mock_get_client, limit):
    data = [{"EventName": f"event-{i}", "CloudTrailEvent": f"event-{i}"} for i in range(123)]
    page_sizes = []

    def fetch(MaxResults, NextToken="0", **kwargs):
        page_sizes.append(MaxResults)
        start = int(NextToken)
        page = data[start:start + MaxResults]
        response = {"Events": page}
        if start + len(page) < len(data):
            response["NextToken"] = str(start + len(page))
        return response

    mock_get_client.return_value.lookup_events.side_effect = fetch
    cursor = None
    messages = []
    for _ in range(130):
        result = cloudtrail_service.lookup_events(
            datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc),
            None, None, limit, cursor, make_settings(),
        )
        assert len(result.events) <= limit
        messages.extend(event.message for event in result.events)
        cursor = result.cursor
        if cursor is None:
            break
    assert cursor is None
    assert messages == [event["CloudTrailEvent"] for event in data]
    assert len(set(page_sizes)) == 1
