import base64
import json
from datetime import datetime, timezone

from app.config import Settings
from app.core.aws_session import get_logs_client
from app.schemas.cloudwatch import (
    CloudWatchSearchResponse,
    LogGroup,
    LogGroupsResponse,
)
from app.schemas.common import LogEvent


def _ms_to_dt(ms: int | None) -> datetime | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


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


def list_log_groups(
    prefix: str | None, next_token: str | None, limit: int
) -> LogGroupsResponse:
    client = get_logs_client()
    kwargs: dict = {"limit": limit}
    if prefix:
        kwargs["logGroupNamePrefix"] = prefix
    if next_token:
        kwargs["nextToken"] = next_token
    resp = client.describe_log_groups(**kwargs)
    groups = [
        LogGroup(
            name=g["logGroupName"],
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
    client = get_logs_client()
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    effective_limit = min(limit, settings.max_log_search_lines)

    if cursor:
        tokens = _decode_cursor(cursor)
        active_groups = list(tokens.keys())
    else:
        tokens = {}
        active_groups = log_group_names

    all_events: list[LogEvent] = []
    next_tokens: dict[str, str] = {}
    for name in active_groups:
        kwargs: dict = {
            "logGroupName": name,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": min(effective_limit, 1000) or 1000,
        }
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern
        token = tokens.get(name)
        if token:
            kwargs["nextToken"] = token
        resp = client.filter_log_events(**kwargs)
        for e in resp.get("events", []):
            all_events.append(
                LogEvent(
                    source="cloudwatch",
                    origin=name,
                    stream_or_key=e.get("logStreamName", ""),
                    timestamp=_ms_to_dt(e.get("timestamp")),
                    message=e.get("message", ""),
                    line_index=0,
                )
            )
        new_token = resp.get("nextToken")
        if new_token:
            next_tokens[name] = new_token

    all_events.sort(key=lambda ev: ev.timestamp or datetime.min.replace(tzinfo=timezone.utc))
    truncated = len(all_events) > effective_limit
    all_events = all_events[:effective_limit]
    for i, ev in enumerate(all_events):
        ev.line_index = i

    return CloudWatchSearchResponse(
        events=all_events,
        cursor=_encode_cursor(next_tokens),
        truncated=truncated,
        total_returned=len(all_events),
    )
