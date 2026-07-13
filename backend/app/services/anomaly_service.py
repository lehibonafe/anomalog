import asyncio
from functools import lru_cache

from app.config import Settings, get_settings
from app.core.errors import LLMQuotaExceededError, LLMRequestError
from app.core.rate_limiter import RateLimiter
from app.schemas.analysis import AnalysisContext, AnalysisResponse, ChunkResult
from app.schemas.common import LogEvent
from app.services import log_filter
from app.services.llm.base import LLMProvider, LLMRateLimited, ProviderDefaults
from app.services.llm.prompt import build_prompt
from app.services.llm.registry import PROVIDERS, get_provider_class


class AnomalyService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._defaults: dict[str, ProviderDefaults] = {
            name: cls.resolve_defaults(settings) for name, cls in PROVIDERS.items()
        }
        self._limiters: dict[str, RateLimiter] = {
            name: RateLimiter(rpm=d.rpm) for name, d in self._defaults.items()
        }

    async def analyze(
        self,
        events: list[LogEvent],
        context: AnalysisContext,
        *,
        provider: str = "gemini",
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> AnalysisResponse:
        provider_cls = get_provider_class(provider)
        defaults = self._defaults[provider]
        effective_model = model or defaults.model
        effective_base_url = base_url or defaults.base_url
        instance = provider_cls(
            api_key=api_key,
            model=effective_model,
            base_url=effective_base_url,
            settings=self.settings,
        )
        limiter = self._limiters[provider]

        relevant, skipped = log_filter.select_relevant(events, self.settings)
        relevant = log_filter.truncate_and_cap(relevant, self.settings)
        chunks = log_filter.chunk(relevant, self.settings)

        findings = []
        warnings: list[str] = []
        analyzed = 0
        for i, chunk_events in enumerate(chunks):
            await limiter.wait()
            try:
                result = await self._call_chunk(chunk_events, context, instance, defaults.max_retries)
                findings.extend(result.findings)
                analyzed += 1
            except LLMQuotaExceededError as e:
                if analyzed == 0:
                    raise LLMQuotaExceededError(
                        f"{provider} rate limit exceeded before any log chunks could be "
                        "analyzed. Wait a bit or narrow the time range, then retry."
                    ) from e
                warnings.append(
                    f"Rate limit hit after {analyzed}/{len(chunks)} chunks: {e.message}"
                )
                break
            except LLMRequestError as e:
                warnings.append(f"Chunk {i} failed and was skipped: {e.message}")
                continue

        return AnalysisResponse(
            findings=findings,
            chunks_analyzed=analyzed,
            chunks_total=len(chunks),
            lines_considered=len(relevant),
            lines_skipped_by_prefilter=skipped,
            model=effective_model,
            warnings=warnings,
        )

    async def _call_chunk(
        self,
        chunk_events: list[LogEvent],
        context: AnalysisContext,
        provider: LLMProvider,
        max_retries: int,
    ) -> ChunkResult:
        prompt = build_prompt(chunk_events, context)
        for attempt in range(max_retries + 1):
            try:
                return await provider.call_chunk(prompt)
            except LLMRateLimited as e:
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt * 5)
                    continue
                raise LLMQuotaExceededError(str(e)) from e
            except (LLMQuotaExceededError, LLMRequestError):
                raise
            except Exception as e:
                raise LLMRequestError(str(e)) from e
        raise LLMRequestError("LLM request failed after retries")


@lru_cache
def get_anomaly_service() -> "AnomalyService":
    """Process-wide singleton so each provider's RateLimiter paces across
    requests, not just within one analyze() call."""
    return AnomalyService(get_settings())
