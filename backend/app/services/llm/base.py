from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas.analysis import ChunkResult

# Applied to every provider's SDK client (timeout=) so an unreachable/slow
# upstream (e.g. a black-holed internal proxy) fails call_chunk within a
# bounded time instead of hanging on the SDK's own default (600s, or
# indefinitely if the TCP connection never resolves) — matters most for
# test_connection, which is meant to be a fast diagnostic. Each client is
# also constructed with max_retries=0: the SDKs retry timeouts/connection
# errors internally by default (on top of this timeout), which would silently
# multiply the wait (timeout * (1 + max_retries)); AnomalyService._call_chunk
# already owns retry policy at the app level, so the SDK's own retries would
# just be redundant, invisible extra latency.
DEFAULT_LLM_TIMEOUT_S = 180.0


class LLMRateLimited(Exception):
    """Internal signal that a provider call hit an upstream rate limit.

    Raised by LLMProvider.call_chunk implementations and caught only by
    AnomalyService's retry loop, which translates it into LLMQuotaExceededError.
    Never an AppError, never reaches FastAPI directly.
    """


@dataclass(frozen=True)
class ProviderDefaults:
    model: str
    rpm: int
    max_retries: int
    base_url: str | None


class LLMProvider(ABC):
    """One instance per analyze() call — never shared across requests, so a
    frontend-supplied api_key never leaks into a process-wide singleton."""

    name: str

    @classmethod
    @abstractmethod
    def resolve_defaults(cls, settings: "Settings") -> ProviderDefaults:
        """Model/RPM/retries/base_url to use when the frontend didn't override them."""

    @abstractmethod
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None,
        settings: "Settings",
    ) -> None:
        """Build the underlying SDK client."""

    @abstractmethod
    async def call_chunk(self, system: str, prompt: str) -> "ChunkResult":
        """Make exactly one upstream call and return a parsed,
        schema-validated ChunkResult. `system` is the static, cacheable
        system-role prompt (app.services.llm.prompt_v3.SYSTEM_PROMPT); `prompt`
        is the per-request user turn. Raise LLMRateLimited on a rate-limit
        response, LLMRequestError on anything else. No retry logic here."""
