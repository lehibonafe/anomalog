import base64
import json
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.core.aws_session import get_cloudtrail_client, get_logs_client
from app.core.errors import BadRequestError
from app.schemas.cloudtrail import CloudTrailSearchResponse, LookupAttributeKey
from app.schemas.common import LogEvent
from app.services.masking import mask_messages_batch

_PAGE_SIZE = 50

_LOOKUP_FIELD_PATHS: dict[LookupAttributeKey, tuple[str, ...]] = {
    "EventId": ("$.eventID",),
    "EventName": ("$.eventName",),
    "ReadOnly": ("$.readOnly",),
    "Username": (
        "$.userIdentity.userName",
        "$.userIdentity.sessionContext.sessionIssuer.userName",
    ),
    "ResourceType": ("$.resources[*].resourceType",),
    "ResourceName": ("$.resources[*].resourceName",),
    "EventSource": ("$.eventSource",),
    "AccessKeyId": ("$.userIdentity.accessKeyId",),
}


def _configured_log_groups(settings: Settings) -> list[str]:
    return [
        identifier.strip()
        for identifier in (settings.cloudtrail_log_group_identifiers or "").split(",")
        if identifier.strip()
    ]


def _log_group_parameter(identifier: str) -> dict[str, str]:
    if identifier.startswith("arn:"):
        return {"logGroupIdentifier": identifier.removesuffix(":*")}
    return {"logGroupName": identifier}


def _encode_cursor(tokens: dict[str, str]) -> str | None:
    if not tokens:
        return None
    raw = json.dumps(tokens).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str | None) -> dict[str, str]:
    if not cursor:
        return {}
    raw = base64.urlsafe_b64decode(cursor.encode())
    return json.loads(raw)


def _filter_pattern(
    lookup_attribute_key: LookupAttributeKey | None,
    lookup_attribute_value: str | None,
) -> str | None:
    if not lookup_attribute_key or not lookup_attribute_value:
        return None

    if lookup_attribute_key == "ReadOnly" and lookup_attribute_value.lower() in {
        "true",
        "false",
    }:
        return f"{{ $.readOnly IS {lookup_attribute_value.upper()} }}"
    else:
        value = json.dumps(lookup_attribute_value)

    comparisons = [
        f"({path} = {value})" for path in _LOOKUP_FIELD_PATHS[lookup_attribute_key]
    ]
    return "{ " + " || ".join(comparisons) + " }"


def _parse_cloudtrail_message(
    message: str,
    fallback_timestamp_ms: int | None,
    log_group: str,
) -> tuple[str, datetime | None, str]:
    try:
        event = json.loads(message)
    except (TypeError, json.JSONDecodeError):
        event = {}
    if not isinstance(event, dict):
        event = {}

    event_time = None
    raw_event_time = event.get("eventTime")
    if isinstance(raw_event_time, str):
        try:
            event_time = datetime.fromisoformat(raw_event_time.replace("Z", "+00:00"))
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if event_time is None and fallback_timestamp_ms is not None:
        event_time = datetime.fromtimestamp(fallback_timestamp_ms / 1000, tz=timezone.utc)

    account_id = event.get("recipientAccountId")
    if not account_id:
        identity = event.get("userIdentity")
        if isinstance(identity, dict):
            account_id = identity.get("accountId")
    region = event.get("awsRegion")
    origin_parts = ["cloudtrail"]
    origin_parts.extend(str(value) for value in (account_id, region) if value)
    if len(origin_parts) == 1:
        origin_parts.append(log_group)

    return str(event.get("eventName") or "CloudTrail"), event_time, ":".join(origin_parts)


def search_events(
    start_time: datetime,
    end_time: datetime,
    lookup_attribute_key: LookupAttributeKey | None,
    lookup_attribute_value: str | None,
    limit: int,
    cursor: str | None,
    settings: Settings,
) -> CloudTrailSearchResponse:
    """Search centralized CloudTrail logs when configured, else event history."""
    log_groups = _configured_log_groups(settings)
    if log_groups:
        return search_centralized_events(
            log_groups=log_groups,
            start_time=start_time,
            end_time=end_time,
            lookup_attribute_key=lookup_attribute_key,
            lookup_attribute_value=lookup_attribute_value,
            limit=limit,
            cursor=cursor,
            settings=settings,
        )
    return lookup_events(
        start_time=start_time,
        end_time=end_time,
        lookup_attribute_key=lookup_attribute_key,
        lookup_attribute_value=lookup_attribute_value,
        limit=limit,
        cursor=cursor,
        settings=settings,
    )


def search_centralized_events(
    log_groups: list[str],
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
    if limit < 1:
        raise BadRequestError("Limit must be at least 1.")

    client = get_logs_client()
    effective_limit = min(limit, settings.max_log_search_lines)
    tokens = _decode_cursor(cursor)
    active_groups = list(tokens) if cursor else list(dict.fromkeys(log_groups))
    pattern = _filter_pattern(lookup_attribute_key, lookup_attribute_value)

    raw_entries: list[tuple[str, datetime | None, str, str]] = []
    next_tokens: dict[str, str] = {}
    for log_group in active_groups:
        remaining = effective_limit - len(raw_entries)
        if remaining <= 0:
            next_tokens[log_group] = tokens.get(log_group, "")
            continue

        kwargs: dict = {
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000),
            "limit": min(remaining, 1000),
        }
        kwargs.update(_log_group_parameter(log_group))
        if pattern:
            kwargs["filterPattern"] = pattern
        token = tokens.get(log_group)
        if token:
            kwargs["nextToken"] = token

        response = client.filter_log_events(**kwargs)
        for log_event in response.get("events", []):
            message = log_event.get("message", "")
            event_name, event_time, origin = _parse_cloudtrail_message(
                message,
                log_event.get("timestamp"),
                log_group,
            )
            raw_entries.append((event_name, event_time, origin, message))
        next_token = response.get("nextToken")
        if next_token:
            next_tokens[log_group] = next_token

    masked_messages = mask_messages_batch([entry[3] for entry in raw_entries], settings)
    events = [
        LogEvent(
            source="cloudtrail",
            origin=origin,
            stream_or_key=event_name,
            timestamp=event_time,
            message=masked,
            line_index=0,
        )
        for (event_name, event_time, origin, _raw), masked in zip(
            raw_entries, masked_messages
        )
    ]
    events.sort(key=lambda event: event.timestamp or datetime.min.replace(tzinfo=timezone.utc))
    for index, event in enumerate(events):
        event.line_index = index

    return CloudTrailSearchResponse(
        events=events,
        cursor=_encode_cursor(next_tokens),
        truncated=False,
        total_returned=len(events),
    )


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

    if limit < 1:
        raise BadRequestError("Limit must be at least 1.")

    client = get_cloudtrail_client()
    effective_limit = min(limit, settings.max_log_search_lines)

    page_size = min(_PAGE_SIZE, effective_limit)
    kwargs: dict = {
        "StartTime": start_time,
        "EndTime": end_time,
        "MaxResults": page_size,
    }
    if lookup_attribute_key and lookup_attribute_value:
        kwargs["LookupAttributes"] = [
            {"AttributeKey": lookup_attribute_key, "AttributeValue": lookup_attribute_value}
        ]
    if cursor:
        kwargs["NextToken"] = cursor

    raw_entries: list[tuple[str, datetime | None, str]] = []
    next_token: str | None = None
    # Keep AWS parameters stable across continuations. Stop before fetching
    # a page that could exceed our remaining capacity; never discard overflow.
    while len(raw_entries) + page_size <= effective_limit:
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
    for i, ev in enumerate(all_events):
        ev.line_index = i

    return CloudTrailSearchResponse(
        events=all_events,
        cursor=next_token,
        truncated=False,
        total_returned=len(all_events),
    )
