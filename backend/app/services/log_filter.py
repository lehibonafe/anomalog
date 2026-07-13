import re

from app.config import Settings
from app.schemas.common import LogEvent

INTERESTING_RE = re.compile(
    r"\b(ERROR|FATAL|EXCEPTION|TRACEBACK|PANIC|CRITICAL|WARN)\b"
    r"|(?:^|\s)at\s+\S+\(.*\)$"
    r"|File \".*\", line \d+"
    r"|\b5\d\d\b"
    r"|timed?[ -]?out|refused|denied",
    re.IGNORECASE,
)

CONTEXT_LINES = 2


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
    """Per-line middle-truncate, then cap total lines and total chars,
    preferring the most recent lines when over budget."""
    truncated = [_truncate_line(e, settings.max_line_length) for e in events]

    if len(truncated) > settings.max_analysis_lines:
        truncated = truncated[-settings.max_analysis_lines :]

    total_chars = 0
    capped: list[LogEvent] = []
    for e in reversed(truncated):
        total_chars += len(e.message)
        if total_chars > settings.max_analysis_chars:
            break
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
