import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.schemas.common import LogEvent

INTERESTING_RE = re.compile(
    r"\b(ERROR|FATAL|EXCEPTION|TRACEBACK|PANIC|CRITICAL|WARN)\b"
    r"|(?:^|\s)at\s+\S+\(.*\)$"
    r"|File \".*\", line \d+"
    r"|\b(?:401|403|408|429|5\d\d)\b"
    r"|timed?[ -]?out|refused|denied",
    re.IGNORECASE,
)

CONTEXT_LINES = 2

_WORD_RE = re.compile(r"[a-z][a-z0-9_.:/-]*", re.IGNORECASE)
_QUERY_STOP_WORDS = {
    "about", "after", "again", "against", "all", "also", "analyze", "and",
    "answer", "are", "before", "between", "could", "count", "current", "did", "does",
    "entry", "event", "explain", "find", "for", "from", "give", "have", "into",
    "investigate", "log", "logs", "many", "most", "next", "number", "overall",
    "please", "record",
    "records", "request", "requests", "review", "service", "show", "that", "the",
    "their", "then", "these", "this", "those", "total", "user", "what", "when",
    "where", "which", "with", "would", "you",
}
_QUERY_ALIASES = (
    {"login", "logon", "signin", "authenticate", "authentication"},
    {"success", "successful", "succeeded", "completed", "ok"},
    {"error", "errors", "failed", "failure", "exception", "fatal"},
    {"stop", "stopped", "terminate", "terminated", "shutdown"},
    {"latency", "slow", "duration", "elapsed", "timeout"},
)
_CAUSAL_QUERY_WORDS = {
    "cause", "caused", "causing", "happened", "impact", "incident", "root", "why",
}
_FULL_DATASET_QUERY_RE = re.compile(
    r"\b(?:how many\s+(?:logs?|events?|entries|records)|"
    r"(?:all|total|overall)\s+(?:logs?|events?|entries|records)|"
    r"(?:summari[sz]e|review|analy[sz]e)\s+(?:all|these|the)\s+(?:logs?|events?)|"
    r"(?:distribution|breakdown)\s+(?:of|across)\s+(?:logs?|events?))\b",
    re.IGNORECASE,
)
_ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?\b",
    re.IGNORECASE,
)
_VOLATILE_FIELD_RE = re.compile(
    r"(?P<prefix>(?<![A-Za-z0-9_])[\"']?"
    r"(?:request|trace|span|event|correlation)[_-]?id[\"']?\s*[=:]\s*[\"']?)"
    r"(?P<value>[^\s,;\"']+)",
    re.IGNORECASE,
)
_STATUS_RE = re.compile(
    r"(?:\bstatus(?:[_ -]?code)?|http\.status_code|response\.status)"
    r"\s*[=:]\s*[\"']?([1-5]\d{2})\b",
    re.IGNORECASE,
)
_HTTP_STATUS_RE = re.compile(r"\bHTTP/\d(?:\.\d)?[\"']?\s+([1-5]\d{2})\b", re.IGNORECASE)
_SERVICE_RE = re.compile(
    r"(?:\bservice(?:[_ -]?name)?|eventSource)\s*[=:]\s*[\"']?"
    r"([A-Za-z0-9_.:/-]{1,80})",
    re.IGNORECASE,
)
_SAFE_SERVICE_VALUE_RE = re.compile(r"[A-Za-z0-9_.:/-]{1,80}")
_STATUS_FIELDS = ("status", "status_code", "statuscode", "http.status_code", "response.status")
_SERVICE_FIELDS = ("service", "service_name", "servicename", "aws.service", "eventsource")


@dataclass(frozen=True)
class CompressionResult:
    events: list[LogEvent]
    source_counts: dict[int, int]
    collapsed: int


class AggregatedLogEvent(LogEvent):
    """Internal-only evidence row; API-submitted LogEvent extras are ignored."""

    occurrence_count: int
    aggregate_first_timestamp: str
    aggregate_last_timestamp: str


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-independent estimate for punctuation-heavy logs."""
    if not text:
        return 0
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def estimate_event_tokens(event: LogEvent) -> int:
    metadata = ""
    occurrence_count = getattr(event, "occurrence_count", 1)
    if occurrence_count > 1:
        metadata = (
            f" occurrences={occurrence_count}"
            f" first={getattr(event, 'aggregate_first_timestamp', 'unknown')}"
            f" last={getattr(event, 'aggregate_last_timestamp', 'unknown')}"
        )
    rendered = f"[{event.line_index}] {event.timestamp or ''}{metadata} {event.message}"
    return estimate_tokens(rendered)


def compact_json(events: list[LogEvent]) -> list[LogEvent]:
    """Minify JSON log messages without dropping fields or changing citations."""
    compacted: list[LogEvent] = []
    for event in events:
        message = event.message.strip()
        if not message.startswith(("{", "[")):
            compacted.append(event)
            continue
        try:
            parsed = json.loads(message)
            candidate = json.dumps(
                parsed, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        except (TypeError, ValueError):
            compacted.append(event)
            continue
        compacted.append(
            event.model_copy(update={"message": candidate})
            if len(candidate) < len(event.message)
            else event
        )
    return compacted


def _flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        flattened[path.lower()] = item
        if isinstance(item, dict):
            flattened.update(_flatten_json(item, path))
    return flattened


def _first_scalar(fields: dict[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = fields.get(name)
        if isinstance(value, (str, int, float)):
            return str(value)
    return None


def derived_counts(events: list[LogEvent]) -> dict[str, dict[str, int]]:
    """Compute compact, deterministic facets that models should not recount."""
    statuses: Counter[str] = Counter()
    services: Counter[str] = Counter()
    service_5xx: Counter[str] = Counter()

    for event in events:
        fields: dict[str, Any] = {}
        message = event.message.strip()
        if message.startswith("{"):
            try:
                fields = _flatten_json(json.loads(message))
            except (TypeError, ValueError):
                fields = {}

        raw_status = _first_scalar(fields, _STATUS_FIELDS)
        if raw_status is None:
            match = _STATUS_RE.search(message) or _HTTP_STATUS_RE.search(message)
            raw_status = match.group(1) if match else None
        status_match = re.fullmatch(r"[1-5]\d{2}", raw_status or "")
        status = status_match.group(0) if status_match else None

        service = _first_scalar(fields, _SERVICE_FIELDS)
        if service is None:
            match = _SERVICE_RE.search(message)
            service = match.group(1) if match else None
        if service and _SAFE_SERVICE_VALUE_RE.fullmatch(service):
            services[service] += 1
        else:
            service = None
        if status:
            statuses[status] += 1
            if status.startswith("5") and service:
                service_5xx[service] += 1

    def top(counter: Counter[str]) -> dict[str, int]:
        return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:20])

    return {
        key: values
        for key, values in (
            ("http_status", top(statuses)),
            ("service", top(services)),
            ("service_5xx", top(service_5xx)),
        )
        if values
    }


def _stem(word: str) -> str:
    word = word.lower().strip("._:/-")
    if len(word) > 5 and word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _query_terms(user_prompt: str) -> set[str]:
    raw = {_stem(word) for word in _WORD_RE.findall(user_prompt)}
    terms = {word for word in raw if len(word) >= 3 and word not in _QUERY_STOP_WORDS}
    for aliases in _QUERY_ALIASES:
        alias_stems = {_stem(alias) for alias in aliases}
        if raw & alias_stems:
            terms.update(alias_stems)
    return terms


def select_for_question(
    events: list[LogEvent], user_prompt: str, settings: Settings
) -> tuple[list[LogEvent], int]:
    """Select lexical matches plus context, with anomaly fallback for recall.

    This replaces the old all-or-nothing behavior where asking any custom
    question disabled filtering and sent the complete visible log slice.
    """
    if not events:
        return [], 0

    if _FULL_DATASET_QUERY_RE.search(user_prompt):
        return list(events), 0

    terms = _query_terms(user_prompt)
    prompt_lower = user_prompt.lower()
    requested_status_families = set(re.findall(r"\b([1-5])xx\b", prompt_lower))
    match_positions: set[int] = set()

    for position, event in enumerate(events):
        message_lower = event.message.lower()
        message_terms = {_stem(word) for word in _WORD_RE.findall(message_lower)}
        if terms & message_terms:
            match_positions.add(position)
            continue
        if any(
            re.search(rf"\b{status_family}\d\d\b", message_lower)
            for status_family in requested_status_families
        ):
            match_positions.add(position)

    if terms & _CAUSAL_QUERY_WORDS:
        match_positions.update(
            position
            for position, event in enumerate(events)
            if INTERESTING_RE.search(event.message)
        )

    if not match_positions:
        return select_relevant(events, settings)

    keep_positions: set[int] = set()
    for position in match_positions:
        for offset in range(-CONTEXT_LINES, CONTEXT_LINES + 1):
            index = position + offset
            if 0 <= index < len(events):
                keep_positions.add(index)

    kept = [events[index] for index in sorted(keep_positions)]
    return kept, len(events) - len(kept)


def _message_signature(message: str) -> str:
    signature = message.lower()
    signature = _ISO_TIMESTAMP_RE.sub("<timestamp>", signature)
    signature = _VOLATILE_FIELD_RE.sub(
        lambda match: f"{match.group('prefix')}<id>", signature
    )
    return " ".join(signature.split())


def compress_duplicates(events: list[LogEvent]) -> CompressionResult:
    """Collapse equivalent events into a counted representative when cheaper.

    Each representative retains a real line index, so citations still navigate
    to the raw log viewer. ``source_counts`` lets coverage reporting count all
    source lines represented by a successful model call.
    """
    groups: dict[tuple[str, str, str, str], list[LogEvent]] = {}
    for event in events:
        key = (
            event.source,
            event.origin,
            event.stream_or_key,
            _message_signature(event.message),
        )
        groups.setdefault(key, []).append(event)

    compressed: list[LogEvent] = []
    source_counts: dict[int, int] = {}
    collapsed = 0
    for group in groups.values():
        representative = group[0]
        if len(group) == 1:
            compressed.append(representative)
            source_counts[representative.line_index] = 1
            continue

        first_timestamp = group[0].timestamp.isoformat() if group[0].timestamp else "unknown"
        last_timestamp = group[-1].timestamp.isoformat() if group[-1].timestamp else "unknown"
        aggregated = AggregatedLogEvent(
            **representative.model_dump(),
            occurrence_count=len(group),
            aggregate_first_timestamp=first_timestamp,
            aggregate_last_timestamp=last_timestamp,
        )
        original_tokens = sum(estimate_event_tokens(event) for event in group)
        if estimate_event_tokens(aggregated) >= original_tokens:
            compressed.extend(group)
            source_counts.update({event.line_index: 1 for event in group})
            continue

        compressed.append(aggregated)
        source_counts[aggregated.line_index] = len(group)
        collapsed += len(group) - 1

    compressed.sort(key=lambda event: event.line_index)
    return CompressionResult(
        events=compressed,
        source_counts=source_counts,
        collapsed=collapsed,
    )


def select_relevant(events: list[LogEvent], settings: Settings) -> tuple[list[LogEvent], int]:
    """Keeps lines matching INTERESTING_RE plus surrounding context lines.
    Falls back to even sampling when nothing matches, so quiet logs still get scanned."""
    if not events:
        return [], 0

    match_positions = {i for i, e in enumerate(events) if INTERESTING_RE.search(e.message)}

    if not match_positions:
        sampled = _even_sample(events, settings.max_analysis_lines)
        return sampled, len(events) - len(sampled)

    keep_positions: set[int] = set()
    for pos in match_positions:
        for offset in range(-CONTEXT_LINES, CONTEXT_LINES + 1):
            idx = pos + offset
            if 0 <= idx < len(events):
                keep_positions.add(idx)

    kept = [events[i] for i in sorted(keep_positions)]
    return kept, len(events) - len(kept)


def _even_sample(events: list[LogEvent], target: int) -> list[LogEvent]:
    if len(events) <= target or target <= 0:
        return list(events)
    stride = len(events) / target
    indices = sorted({int(i * stride) for i in range(target)})
    return [events[i] for i in indices]


def truncate_and_cap(events: list[LogEvent], settings: Settings) -> list[LogEvent]:
    """Per-line truncate, then enforce line, character, and token budgets."""
    truncated = [_truncate_line(e, settings.max_line_length) for e in events]

    if len(truncated) > settings.max_analysis_lines:
        truncated = truncated[-settings.max_analysis_lines :]

    total_chars = 0
    total_tokens = 0
    capped: list[LogEvent] = []
    for e in reversed(truncated):
        event_chars = len(e.message)
        event_tokens = estimate_event_tokens(e)
        if (
            total_chars + event_chars > settings.max_analysis_chars
            or total_tokens + event_tokens > settings.max_analysis_tokens
        ):
            break
        total_chars += event_chars
        total_tokens += event_tokens
        capped.append(e)
    capped.reverse()
    return capped


def _truncate_line(event: LogEvent, max_length: int) -> LogEvent:
    if len(event.message) <= max_length:
        return event
    half = (max_length - 5) // 2
    truncated_msg = event.message[:half] + " ... " + event.message[-half:]
    return event.model_copy(update={"message": truncated_msg})


def chunk(events: list[LogEvent], settings: Settings) -> list[list[LogEvent]]:
    """Splits into at most gemini_max_chunks_per_analysis chunks of chunk_size_lines each.
    Overflow beyond the chunk cap is dropped; caller is responsible for reporting it."""
    if not events:
        return []
    chunks = [
        events[i : i + settings.chunk_size_lines]
        for i in range(0, len(events), settings.chunk_size_lines)
    ]
    return chunks[: settings.gemini_max_chunks_per_analysis]
