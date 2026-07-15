from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.core.errors import BadRequestError
from app.services import cloudtrail_service


def make_settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


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
