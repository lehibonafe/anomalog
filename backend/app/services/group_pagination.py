"""Merge paginated CloudWatch log groups without losing cross-group order."""

import base64
import binascii
import json
import zlib
from collections.abc import Callable
from datetime import datetime, timezone

from app.core.errors import BadRequestError
from app.schemas.common import LogEvent

_BATCH_SIZE = 100
_MAX_CURSOR_BYTES = 8_000_000


def _encode(states: list[dict], query_key: str) -> str | None:
    active = [state for state in states if state["pending"] or not state["done"]]
    if not active:
        return None
    payload = json.dumps({"version": 1, "query": query_key, "groups": active}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(zlib.compress(payload)).decode()


def _decode(cursor: str, query_key: str | None = None) -> list[dict]:
    try:
        compressed = base64.urlsafe_b64decode(cursor.encode())
        if len(compressed) > _MAX_CURSOR_BYTES:
            raise ValueError("Cursor is too large")
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, _MAX_CURSOR_BYTES + 1)
        if len(raw) > _MAX_CURSOR_BYTES or not inflater.eof:
            raise ValueError("Cursor is too large or incomplete")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("groups"), list):
            raise ValueError("Unsupported cursor")
        if query_key is not None and payload.get("query") != query_key:
            raise ValueError("Cursor does not match this search")
        states = payload["groups"]
        for state in states:
            if not isinstance(state, dict) or not isinstance(state.get("name"), str):
                raise ValueError("Invalid group")
            if state.get("token") is not None and not isinstance(state["token"], str):
                raise ValueError("Invalid token")
            if not isinstance(state.get("done"), bool) or not isinstance(state.get("pending"), list):
                raise ValueError("Invalid pending events")
            state["pending"] = [LogEvent.model_validate(event).model_dump(mode="json") for event in state["pending"]]
        return states
    except (ValueError, TypeError, KeyError, binascii.Error, zlib.error) as error:
        raise BadRequestError("Invalid or expired search cursor.") from error


def cursor_tokens(cursor: str | None) -> dict[str, str]:
    """Expose AWS tokens for diagnostics and existing service tests."""
    return {state["name"]: state["token"] or "" for state in _decode(cursor)} if cursor else {}


def merge_group_pages(
    *,
    groups: list[str],
    limit: int,
    cursor: str | None,
    query_key: str,
    fetch_page: Callable[[str, str | None, int], dict],
    convert_page: Callable[[str, list[dict]], list[LogEvent]],
    remask_pending: Callable[[list[str]], list[str]],
) -> tuple[list[LogEvent], str | None]:
    states = _decode(cursor, query_key) if cursor else [
        {"name": name, "token": None, "pending": [], "done": False}
        for name in dict.fromkeys(groups)
    ]
    if cursor:
        for state in states:
            if state["pending"]:
                messages = [event["message"] for event in state["pending"]]
                for event, masked in zip(state["pending"], remask_pending(messages)):
                    event["message"] = masked
    result: list[LogEvent] = []
    def first_timestamp(state: dict) -> datetime:
        value = state["pending"][0]["timestamp"]
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else datetime.min.replace(tzinfo=timezone.utc)

    while len(result) < limit:
        unresolved = False
        for state in states:
            if state["pending"] or state["done"]:
                continue
            previous_token = state["token"]
            active_count = sum(bool(group["pending"]) or not group["done"] for group in states)
            page_size = min(limit, max(1, _BATCH_SIZE // max(1, active_count)))
            response = fetch_page(state["name"], previous_token, page_size)
            raw_events = response.get("events", [])
            state["token"] = response.get("nextToken")
            state["done"] = not bool(state["token"])
            if raw_events:
                converted = convert_page(state["name"], raw_events)
                converted.sort(key=lambda event: event.timestamp or datetime.min.replace(tzinfo=timezone.utc))
                state["pending"] = [event.model_dump(mode="json") for event in converted]
            elif not state["done"] and state["token"] == previous_token:
                raise BadRequestError("CloudWatch pagination did not advance.")
            if not state["pending"] and not state["done"]:
                unresolved = True

        # An unresolved group may contain an earlier event; return an empty
        # continuation page instead of presenting later events out of order.
        if unresolved:
            break
        candidates = [state for state in states if state["pending"]]
        if not candidates:
            break
        selected = min(
            candidates,
            key=lambda state: (first_timestamp(state), states.index(state)),
        )
        result.append(LogEvent.model_validate(selected["pending"].pop(0)))

    for index, event in enumerate(result):
        event.line_index = index
    return result, _encode(states, query_key)
