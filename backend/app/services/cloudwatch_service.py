import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.core.aws_session import get_logs_client
from app.core.errors import BadRequestError
from app.schemas.cloudwatch import (
    CloudWatchSearchResponse,
    LogGroup,
    LogGroupsResponse,
)
from app.schemas.common import LogEvent
from app.services.masking import mask_messages_batch
from app.services.group_pagination import cursor_tokens, merge_group_pages


def _ms_to_dt(ms: int | None) -> datetime | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _normalize_log_group_arn(arn: str) -> str:
    """Return the log-group ARN form accepted by cross-account read APIs."""
    return arn.removesuffix(":*")


def _account_id_from_identifier(identifier: str) -> str | None:
    if not identifier.startswith("arn:"):
        return None
    parts = identifier.split(":", 5)
    return parts[4] if len(parts) == 6 else None


def _display_log_group(identifier: str) -> str:
    if ":log-group:" in identifier:
        return identifier.split(":log-group:", 1)[1].removesuffix(":*")
    return identifier


def _log_group_parameter(identifier: str) -> dict[str, str]:
    if identifier.startswith("arn:"):
        return {"logGroupIdentifier": _normalize_log_group_arn(identifier)}
    return {"logGroupName": identifier}


def _decode_cursor(cursor: str | None) -> dict[str, str]:
    return cursor_tokens(cursor)


def list_log_groups(
    keyword: str | None,
    next_token: str | None,
    limit: int,
    settings: Settings,
) -> LogGroupsResponse:
    client = get_logs_client()
    kwargs: dict = {"limit": limit}
    if settings.aws_include_linked_accounts:
        kwargs["includeLinkedAccounts"] = True
    if keyword:
        kwargs["logGroupNamePattern"] = keyword
    if next_token:
        kwargs["nextToken"] = next_token
    resp = client.describe_log_groups(**kwargs)
    groups = [
        LogGroup(
            name=g["logGroupName"],
            identifier=_normalize_log_group_arn(
                g.get("logGroupArn") or g.get("arn") or g["logGroupName"]
            ),
            account_id=_account_id_from_identifier(g.get("logGroupArn") or g.get("arn", "")),
            stored_bytes=g.get("storedBytes"),
            creation_time=_ms_to_dt(g.get("creationTime")),
        )
        for g in resp.get("logGroups", [])
    ]
    return LogGroupsResponse(log_groups=groups, next_token=resp.get("nextToken"))


def search_log_events(
    log_group_names: list[str],
    start_time: datetime,
    end_time: datetime,
    filter_pattern: str | None,
    limit: int,
    cursor: str | None,
    settings: Settings,
) -> CloudWatchSearchResponse:
    max_range = timedelta(days=settings.max_time_range_days)
    if end_time - start_time > max_range:
        raise BadRequestError(
            f"Time range too large: max {settings.max_time_range_days} days between "
            "start and end (CloudWatch Logs scanning is billed by data scanned across "
            "the range)."
        )

    if limit < 1:
        raise BadRequestError("Limit must be at least 1.")

    client = get_logs_client()
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    effective_limit = min(limit, settings.max_log_search_lines)

    def fetch_page(name: str, token: str | None, page_limit: int) -> dict:
        kwargs: dict = {
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": page_limit,
        }
        kwargs.update(_log_group_parameter(name))
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern
        if token:
            kwargs["nextToken"] = token
        return client.filter_log_events(**kwargs)

    def convert_page(name: str, raw_events: list[dict]) -> list[LogEvent]:
        masked = mask_messages_batch([event.get("message", "") for event in raw_events], settings)
        return [
            LogEvent(
                source="cloudwatch",
                origin=_display_log_group(name),
                stream_or_key=event.get("logStreamName", ""),
                timestamp=_ms_to_dt(event.get("timestamp")),
                message=message,
                line_index=0,
                )
            for event, message in zip(raw_events, masked)
        ]

    all_events, next_cursor = merge_group_pages(
        groups=log_group_names,
        limit=effective_limit,
        cursor=cursor,
        query_key=hashlib.sha256(json.dumps([
            list(dict.fromkeys(log_group_names)), start_ms, end_ms, filter_pattern,
        ], separators=(",", ":")).encode()).hexdigest(),
        fetch_page=fetch_page,
        convert_page=convert_page,
        remask_pending=lambda messages: mask_messages_batch(messages, settings),
    )

    return CloudWatchSearchResponse(
        events=all_events,
        cursor=next_cursor,
        truncated=False,
        total_returned=len(all_events),
    )
