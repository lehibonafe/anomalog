from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.core.aws_session import get_cloudtrail_client
from app.core.errors import BadRequestError
from app.schemas.cloudtrail import CloudTrailSearchResponse, LookupAttributeKey
from app.schemas.common import LogEvent
from app.services.masking import mask_messages_batch

_PAGE_SIZE = 50


def lookup_events(
    start_time: datetime,
    end_time: datetime,
    lookup_attribute_key: LookupAttributeKey | None,
    lookup_attribute_value: str | None,
    limit: int,
    cursor: str | None,
    settings: Settings,
) -> CloudTrailSearchResponse:
    max_range = timedelta(days=settings.max_time_range_days)
    if end_time - start_time > max_range:
        raise BadRequestError(
            f"Time range too large: max {settings.max_time_range_days} days between "
            "start and end."
        )

    client = get_cloudtrail_client()
    effective_limit = min(limit, settings.max_log_search_lines)

    kwargs: dict = {
        "StartTime": start_time,
        "EndTime": end_time,
        "MaxResults": _PAGE_SIZE,
    }
    if lookup_attribute_key and lookup_attribute_value:
        kwargs["LookupAttributes"] = [
            {"AttributeKey": lookup_attribute_key, "AttributeValue": lookup_attribute_value}
        ]
    if cursor:
        kwargs["NextToken"] = cursor

    raw_entries: list[tuple[str, datetime | None, str]] = []
    next_token: str | None = None
    while len(raw_entries) < effective_limit:
        resp = client.lookup_events(**kwargs)
        for e in resp.get("Events", []):
            event_time = e.get("EventTime")
            raw_entries.append(
                (
                    e.get("EventName", ""),
                    event_time.astimezone(timezone.utc) if event_time else None,
                    e.get("CloudTrailEvent", ""),
                )
            )
        next_token = resp.get("NextToken")
        if not next_token:
            break
        kwargs["NextToken"] = next_token

    masked_messages = mask_messages_batch([r[2] for r in raw_entries], settings)
    all_events: list[LogEvent] = [
        LogEvent(
            source="cloudtrail",
            origin="cloudtrail",
            stream_or_key=event_name,
            timestamp=timestamp,
            message=masked,
            line_index=0,
        )
        for (event_name, timestamp, _raw), masked in zip(raw_entries, masked_messages)
    ]

    all_events.sort(key=lambda ev: ev.timestamp or datetime.min.replace(tzinfo=timezone.utc))
    truncated = len(all_events) > effective_limit
    all_events = all_events[:effective_limit]
    for i, ev in enumerate(all_events):
        ev.line_index = i

    return CloudTrailSearchResponse(
        events=all_events,
        cursor=next_token,
        truncated=truncated,
        total_returned=len(all_events),
    )
