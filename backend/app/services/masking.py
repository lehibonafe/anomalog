"""Masks credentials/secrets and PII in log message text.

Applied unconditionally at the source (cloudwatch_service/s3_service) before
line_index is assigned, so the masked text is what both the UI displays and
what gets sent to any LLM provider for analysis — see the line-index contract
in CLAUDE.md.
"""

import re

MASK = "***MASKED***"

_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER_RE = re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9\-\._~+/]+=*")
_BASIC_AUTH_RE = re.compile(r"(?i)\b(Basic)\s+[A-Za-z0-9+/]+=*")

_SECRET_KEY_VALUE_RE = re.compile(
    r"(?i)(['\"]?\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key(?:[_-]?id)?|"
    r"secret[_-]?access[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"private[_-]?key|session[_-]?token)\b['\"]?)"
    r"(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
_CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_card_candidate(m: re.Match) -> str:
    digits = re.sub(r"[ -]", "", m.group(0))
    if 13 <= len(digits) <= 19 and _luhn_valid(digits):
        return MASK
    return m.group(0)


def mask_message(text: str) -> str:
    text = _AWS_ACCESS_KEY_RE.sub(MASK, text)
    text = _JWT_RE.sub(MASK, text)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)} {MASK}", text)
    text = _BASIC_AUTH_RE.sub(lambda m: f"{m.group(1)} {MASK}", text)
    text = _SECRET_KEY_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)
    text = _EMAIL_RE.sub(MASK, text)
    text = _SSN_RE.sub(MASK, text)
    text = _CARD_CANDIDATE_RE.sub(_mask_card_candidate, text)
    text = _PHONE_RE.sub(MASK, text)
    return text
