import json

from app.schemas.analysis import AnalysisContext, ChunkResult
from app.schemas.common import LogEvent

_SCHEMA_HINT = json.dumps(ChunkResult.model_json_schema())


def build_prompt(
    events: list[LogEvent],
    context: AnalysisContext,
    user_prompt: str | None = None,
) -> str:
    lines = "\n".join(f"[{e.line_index}] {e.timestamp or ''} {e.message}" for e in events)
    if user_prompt:
        instruction = (
            "Answer the user's request below about these logs, reporting each relevant "
            "occurrence or conclusion as a finding that cites the lines supporting it.\n"
            f"USER REQUEST: {user_prompt}\n"
        )
    else:
        instruction = (
            "Identify errors, exceptions, stack traces, and unusual/anomalous patterns "
            "(unexpected status codes, repeated failures, security-relevant events, sudden "
            "behavior changes).\n"
        )
    return (
        "You are a log analysis assistant reviewing a slice of application logs from:\n"
        f"{context.source_description}\n\n"
        'Each line below is prefixed with its index in square brackets, e.g. "[42]".\n'
        f"{instruction}"
        "For each finding's severity, use whatever word or short phrase best describes "
        "how serious it is — you are not limited to a fixed set of severity labels.\n"
        "Reference EXACT line_index values from the brackets — never invent an index. "
        "If nothing matches, return an empty findings list.\n"
        "Return ONLY JSON matching this schema (no prose, no markdown fences):\n"
        f"{_SCHEMA_HINT}\n\n"
        "LOGS:\n"
        f"{lines}"
    )
