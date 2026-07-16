from app.schemas.analysis import AnalysisContext
from app.schemas.common import LogEvent


def build_prompt(
    events: list[LogEvent],
    context: AnalysisContext,
    user_prompt: str | None = None,
) -> str:
    lines = "\n".join(f"[{e.line_index}] {e.timestamp or ''} {e.message}" for e in events)
    if user_prompt:
        instruction = (
            "Answer the user's request below about these logs, writing a plain-language "
            "analysis of what you find.\n"
            f"USER REQUEST: {user_prompt}\n"
        )
    else:
        instruction = (
            "Write a plain-language analysis identifying errors, exceptions, stack traces, "
            "and unusual/anomalous patterns (unexpected status codes, repeated failures, "
            "security-relevant events, sudden behavior changes).\n"
        )
    return (
        "You are a log analysis assistant reviewing a slice of application logs from:\n"
        f"{context.source_description}\n\n"
        'Each line below is prefixed with its index in square brackets, e.g. "[42]".\n'
        f"{instruction}"
        "Respond with plain prose, not JSON or markdown — write it as you would explain it "
        "to a teammate. When you refer to specific lines, cite their EXACT bracketed index "
        'inline, e.g. "[42]" or "[42-45]" for a range, so the reader can jump straight to '
        "them — never invent an index that isn't in the brackets above. If nothing "
        "noteworthy is present, say so plainly instead of listing findings.\n\n"
        "LOGS:\n"
        f"{lines}"
    )
