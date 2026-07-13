from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas.analysis import ChunkResult


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
    async def call_chunk(self, prompt: str) -> "ChunkResult":
        """Make exactly one upstream call for one prompt and return a parsed,
        schema-validated ChunkResult. Raise LLMRateLimited on a rate-limit
        response, LLMRequestError on anything else. No retry logic here."""
