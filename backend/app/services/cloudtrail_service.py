import json
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.core.aws_session import get_cloudtrail_client, get_logs_client
from app.core.errors import BadRequestError
from app.schemas.cloudtrail import (
    CloudTrailAccountId,
    CloudTrailSearchResponse,
    LookupAttributeKey,
)
from app.schemas.common import LogEvent
from app.services.masking import mask_messages_batch
from app.services.group_pagination import merge_group_pages

_PAGE_SIZE = 50

_CLOUDTRAIL_ACCOUNT_LOG_GROUPS: dict[CloudTrailAccountId, tuple[str, str]] = {
    "887350548529": ("ETAP DEVOPS", "aws-cloudtrail-logs-887350548529-f604b9db"),
    "065031412132": ("ETAP ECPAY", "aws-cloudtrail-logs-065031412132-e541306b"),
    "221315724874": ("ETAP INC", "aws-cloudtrail-logs-221315724874-03b2f0ba"),
    "550222016520": ("ETAP MONITORING", "MONITORING-CLOUDTRAIL-EVENTS-LOGS"),
    "679437835821": ("ETAP SRE", "aws-cloudtrail-logs-679437835821-c90511d5"),
    "765186506449": ("ETAP SYSOPS", "aws-cloudtrail-logs-765186506449-5913834d"),
}

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


def _account_id_from_arn(arn: str) -> str | None:
    parts = arn.split(":", 5)
    return parts[4] if len(parts) == 6 else None


def _discover_log_groups(
    client,
    account_id: CloudTrailAccountId | None,
) -> list[str]:
    targets = (
        {account_id: _CLOUDTRAIL_ACCOUNT_LOG_GROUPS[account_id]}
        if account_id
        else _CLOUDTRAIL_ACCOUNT_LOG_GROUPS
    )
    discovered: dict[str, str] = {}

    for expected_account_id, (account_name, log_group_name) in targets.items():
        next_token = None
        while True:
            kwargs: dict = {
                "includeLinkedAccounts": True,
                "logGroupNamePattern": log_group_name,
                "limit": 50,
            }
            if next_token:
                kwargs["nextToken"] = next_token
            response = client.describe_log_groups(**kwargs)
            for group in response.get("logGroups", []):
                arn = group.get("logGroupArn") or group.get("arn", "")
                if (
                    group.get("logGroupName") == log_group_name
                    and _account_id_from_arn(arn) == expected_account_id
                ):
                    discovered[expected_account_id] = arn.removesuffix(":*")
            next_token = response.get("nextToken")
            if not next_token:
                break

        if expected_account_id not in discovered:
            raise BadRequestError(
                f"CloudTrail log group not found for {account_name} "
                f"({expected_account_id}): {log_group_name}."
            )

    return list(discovered.values())


def _log_group_parameter(identifier: str) -> dict[str, str]:
    if identifier.startswith("arn:"):
        return {"logGroupIdentifier": identifier.removesuffix(":*")}
    return {"logGroupName": identifier}


def _filter_pattern(
    lookup_attribute_key: LookupAttributeKey | None,
    lookup_attribute_value: str | None,
    account_id: CloudTrailAccountId | None = None,
) -> str | None:
    conditions: list[str] = []
    if account_id:
        conditions.append(f"($.recipientAccountId = {json.dumps(account_id)})")

    if lookup_attribute_key and lookup_attribute_value:
        if lookup_attribute_key == "ReadOnly" and lookup_attribute_value.lower() in {
            "true",
            "false",
        }:
            conditions.append(f"($.readOnly IS {lookup_attribute_value.upper()})")
        else:
            value = json.dumps(lookup_attribute_value)
            comparisons = [
                f"({path} = {value})"
                for path in _LOOKUP_FIELD_PATHS[lookup_attribute_key]
            ]
            if len(comparisons) == 1:
                conditions.append(comparisons[0])
            else:
                conditions.append("(" + " || ".join(comparisons) + ")")

    if not conditions:
        return None
    return "{ " + " && ".join(conditions) + " }"


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
    account_id: CloudTrailAccountId | None = None,
) -> CloudTrailSearchResponse:
    """Search centralized CloudTrail logs when configured, else event history."""
    log_groups = _configured_log_groups(settings)
    if not log_groups and settings.aws_include_linked_accounts:
        # A continuation cursor already contains the exact group ARNs, so only
        # discover on the first page of a search.
        log_groups = [] if cursor else _discover_log_groups(get_logs_client(), account_id)
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
            account_id=account_id,
        )
    if cursor and settings.aws_include_linked_accounts:
        return search_centralized_events(
            log_groups=[],
            start_time=start_time,
            end_time=end_time,
            lookup_attribute_key=lookup_attribute_key,
            lookup_attribute_value=lookup_attribute_value,
            limit=limit,
            cursor=cursor,
            settings=settings,
            account_id=account_id,
        )
    if account_id:
        raise BadRequestError(
            "CloudTrail account selection requires centralized CloudWatch log groups."
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
    account_id: CloudTrailAccountId | None = None,
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
    pattern = _filter_pattern(
        lookup_attribute_key,
        lookup_attribute_value,
        account_id,
    )

    def fetch_page(log_group: str, token: str | None, page_limit: int) -> dict:
        kwargs: dict = {
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000),
            "limit": page_limit,
        }
        kwargs.update(_log_group_parameter(log_group))
        if pattern:
            kwargs["filterPattern"] = pattern
        if token:
            kwargs["nextToken"] = token
        return client.filter_log_events(**kwargs)

    def convert_page(log_group: str, raw_events: list[dict]) -> list[LogEvent]:
        parsed = []
        for log_event in raw_events:
            message = log_event.get("message", "")
            event_name, event_time, origin = _parse_cloudtrail_message(
                message,
                log_event.get("timestamp"),
                log_group,
            )
            parsed.append((event_name, event_time, origin, message))
        masked_messages = mask_messages_batch([entry[3] for entry in parsed], settings)
        return [
            LogEvent(
                source="cloudtrail",
                origin=origin,
                stream_or_key=event_name,
                timestamp=event_time,
                message=masked,
                line_index=0,
            )
            for (event_name, event_time, origin, _raw), masked in zip(parsed, masked_messages)
        ]

    events, next_cursor = merge_group_pages(
        groups=log_groups,
        limit=effective_limit,
        cursor=cursor,
        fetch_page=fetch_page,
        convert_page=convert_page,
    )

    return CloudTrailSearchResponse(
        events=events,
        cursor=next_cursor,
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
