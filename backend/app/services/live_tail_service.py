"""CloudWatch Logs Live Tail streaming helpers.

The boto3 Live Tail API is a blocking event stream, so callers run
``stream_live_tail`` in a worker thread and forward emitted messages to their
async transport. Closing ``stream_holder['stream']`` terminates the underlying
AWS connection promptly when the browser disconnects.
"""

from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timezone
import asyncio
import threading
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.core.aws_session import get_logs_client
from app.services.masking import mask_messages_batch

LiveTailMessageEmitter = Callable[[dict[str, Any]], None]


class LiveTailSessionLimiter:
    """Small per-process concurrency guard for billable Live Tail sessions."""

    def __init__(self) -> None:
        self._active = 0
        self._lock = asyncio.Lock()

    @property
    def active(self) -> int:
        return self._active

    async def acquire(self, limit: int) -> bool:
        async with self._lock:
            if self._active >= max(1, limit):
                return False
            self._active += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)


def _resolve_log_group_identifiers(client, log_group_names: list[str]) -> dict[str, str]:
    """Return Live Tail ARN -> display-name mappings for exact log groups."""
    resolved: dict[str, str] = {}
    for name in dict.fromkeys(log_group_names):
        response = client.describe_log_groups(logGroupNamePrefix=name, limit=50)
        group = next(
            (item for item in response.get("logGroups", []) if item.get("logGroupName") == name),
            None,
        )
        if not group:
            raise ValueError(f"CloudWatch log group not found: {name}")
        identifier = group.get("logGroupArn") or str(group.get("arn", "")).removesuffix(":*")
        if not identifier:
            raise ValueError(f"CloudWatch did not return an ARN for log group: {name}")
        resolved[identifier] = name
    return resolved


def _timestamp_iso(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def _display_group(identifier: str, resolved: dict[str, str]) -> str:
    if identifier in resolved:
        return resolved[identifier]
    if ":log-group:" in identifier:
        return identifier.split(":log-group:", 1)[1].removesuffix(":*")
    return identifier


def stream_live_tail(
    *,
    log_group_names: list[str],
    filter_pattern: str | None,
    settings: Settings,
    emit: LiveTailMessageEmitter,
    stop_event: threading.Event,
    stream_holder: dict[str, Any],
) -> None:
    """Stream masked Live Tail events until AWS ends or ``stop_event`` is set."""
    try:
        client = get_logs_client()
        resolved = _resolve_log_group_identifiers(client, log_group_names)
        kwargs: dict[str, Any] = {"logGroupIdentifiers": list(resolved)}
        if filter_pattern:
            kwargs["logEventFilterPattern"] = filter_pattern

        response = client.start_live_tail(**kwargs)
        response_stream = response["responseStream"]
        stream_holder["stream"] = response_stream

        for message in response_stream:
            if stop_event.is_set():
                break

            if "sessionStart" in message:
                emit({"type": "session_started"})
                continue

            if "sessionUpdate" in message:
                update = message["sessionUpdate"]
                raw_events = update.get("sessionResults", [])
                masked = mask_messages_batch(
                    [event.get("message", "") for event in raw_events], settings
                )
                events = [
                    {
                        "source": "cloudwatch",
                        "origin": _display_group(event.get("logGroupIdentifier", ""), resolved),
                        "stream_or_key": event.get("logStreamName", ""),
                        "timestamp": _timestamp_iso(event.get("timestamp")),
                        "message": masked_message,
                        "line_index": 0,
                    }
                    for event, masked_message in zip(raw_events, masked)
                ]
                if events:
                    emit(
                        {
                            "type": "events",
                            "events": events,
                            "sampled": bool(update.get("sessionMetadata", {}).get("sampled", False)),
                        }
                    )
                continue

            error = message.get("SessionTimeoutException") or message.get(
                "SessionStreamingException"
            )
            if error:
                emit({"type": "error", "message": error.get("message", "AWS ended Live Tail")})
                return

        if not stop_event.is_set():
            emit({"type": "session_ended", "reason": "AWS ended the Live Tail session."})
    except (BotoCoreError, ClientError, KeyError, ValueError) as error:
        emit({"type": "error", "message": str(error)})
    finally:
        stream = stream_holder.pop("stream", None)
        close = getattr(stream, "close", None)
        if callable(close):
            with suppress(Exception):
                close()
