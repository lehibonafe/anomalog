import asyncio
import re
from functools import lru_cache

from app.config import Settings, get_settings
from app.core.errors import BadRequestError, LLMQuotaExceededError, LLMRequestError
from app.core.rate_limiter import RateLimiter
from app.schemas.analysis import (
    AnalysisContext,
    AnalysisResponse,
    ChatMessage,
    ChunkResult,
    TestConnectionResponse,
)
from app.schemas.common import LogEvent
from app.services import log_filter
from app.services.llm.base import LLMProvider, LLMRateLimited, ProviderDefaults
from app.services.llm.prompt_v5 import (
    REDUCTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_prompt,
    build_reduction_prompt,
)
from app.services.llm.registry import PROVIDERS, get_provider_class
from app.services.masking import mask_message


_OUTPUT_HEADING_RE = re.compile(
    r'^(?:(?:#{1,6}|\*{1,2})\s*)?'
    r'(?:summary|key findings|likely impact|recommended next steps|evidence gaps)'
    r'(?:\*{1,2})?\s*:?\s*',
    re.IGNORECASE,
)
_LIST_PREFIX_RE = re.compile(r'^(?:[-*•]\s+|\d+[.)]\s+)')
_SEVERITY_RE = re.compile(r'^[\[(]?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\b', re.IGNORECASE)
_SEVERITY_RANK = {
    'CRITICAL': 5,
    'HIGH': 4,
    'MEDIUM': 3,
    'LOW': 2,
    'INFO': 1,
}
_ABBREVIATIONS = {'e.g.', 'i.e.', 'etc.', 'vs.', 'approx.', 'u.s.'}
_CLOSING_PUNCTUATION = '\'’”)]}'
_MAX_RESULT_WORDS = 30


def _first_sentence_end(text: str) -> int | None:
    for index, char in enumerate(text):
        if char not in '.!?':
            continue
        next_index = index + 1
        while next_index < len(text) and text[next_index] in _CLOSING_PUNCTUATION:
            next_index += 1
        if next_index < len(text) and not text[next_index].isspace():
            continue
        token_start = text.rfind(' ', 0, index) + 1
        token = text[token_start : index + 1].lower().lstrip('([\'“')
        if char == '.' and token in _ABBREVIATIONS:
            continue
        return next_index
    return None


def _normalize_one_sentence(text: str) -> str:
    sentence = ' '.join(text.split()).strip()
    if not sentence:
        return ''

    while True:
        without_heading = _OUTPUT_HEADING_RE.sub('', sentence, count=1).strip()
        if without_heading == sentence:
            break
        sentence = without_heading
    sentence = _LIST_PREFIX_RE.sub('', sentence, count=1).strip()

    end = _first_sentence_end(sentence)
    if end is not None:
        sentence = sentence[:end].strip()
    else:
        sentence = sentence.rstrip(' ,;:-')

    words = sentence.split()
    if len(words) > _MAX_RESULT_WORDS:
        sentence = ' '.join(words[:_MAX_RESULT_WORDS]).rstrip(' ,;:.!?') + '.'
    return sentence


def _select_best_analysis(analyses: list[str]) -> str:
    candidates = [_normalize_one_sentence(analysis) for analysis in analyses]
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return ''

    def severity(candidate: str) -> int:
        match = _SEVERITY_RE.match(candidate)
        return _SEVERITY_RANK.get(match.group(1).upper(), 0) if match else 0

    return max(candidates, key=severity)


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
        provider: str = "litellm",
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        user_prompt: str | None = None,
        history: list[ChatMessage] | None = None,
    ) -> AnalysisResponse:
        if len(events) > self.settings.max_log_search_lines:
            raise BadRequestError(
                f"Too many events in one analysis request ({len(events)}); "
                f"max is {self.settings.max_log_search_lines}."
            )
        history = history or []
        if len(history) > self.settings.max_chat_history_messages:
            raise BadRequestError(
                f"Too many messages in conversation history ({len(history)}); "
                f"max is {self.settings.max_chat_history_messages}."
            )

        # Defense in depth: masking.py is applied when events are first fetched
        # from CloudWatch/CloudTrail, but this endpoint accepts a raw events
        # array from the client — re-mask here so a caller that bypasses the
        # normal fetch path can't leak unmasked secrets/PII to an LLM provider.
        # mask_message is idempotent, so this is a no-op for already-masked text.
        events = [e.model_copy(update={"message": mask_message(e.message)}) for e in events]

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

        if user_prompt:
            # the regex prefilter is tuned to the default anomaly scan and
            # could drop the very lines a custom request asks about
            relevant, skipped = events, 0
        else:
            relevant, skipped = log_filter.select_relevant(events, self.settings)
        selected_count = len(relevant)
        relevant = log_filter.truncate_and_cap(relevant, self.settings)
        chunks = log_filter.chunk(relevant, self.settings)

        analyses: list[str] = []
        scheduled = [event for chunk_events in chunks for event in chunk_events]
        omitted = selected_count - len(scheduled)
        original_lengths = {event.line_index: len(event.message) for event in events}
        shortened = sum(
            len(event.message) < original_lengths[event.line_index] for event in scheduled
        )
        warnings: list[str] = []
        if omitted:
            warnings.append(f"Processing limits excluded {omitted} selected log lines.")
        if shortened:
            warnings.append(f"{shortened} scheduled log lines were shortened before analysis.")
        analyzed = 0
        lines_analyzed = 0
        for i, chunk_events in enumerate(chunks):
            await limiter.wait()
            try:
                result = await self._call_chunk(
                    chunk_events, context, instance, defaults.max_retries, user_prompt, history
                )
                analyses.append(result.analysis)
                analyzed += 1
                lines_analyzed += len(chunk_events)
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

        if analyses:
            overview = _select_best_analysis(analyses)
            if len(analyses) > 1:
                await limiter.wait()
                try:
                    result = await self._reduce_analyses(
                        analyses, instance, defaults.max_retries
                    )
                    reduced = _normalize_one_sentence(result.analysis)
                    if reduced:
                        overview = reduced
                    else:
                        warnings.append(
                            'The final summary was empty; showing the strongest chunk result.'
                        )
                except (LLMQuotaExceededError, LLMRequestError) as e:
                    warnings.append(
                        'Could not consolidate all analyzed chunks; showing the '
                        f'strongest chunk result instead: {e.message}'
                    )
            analyses = [overview] if overview else []

        return AnalysisResponse(
            analysis="\n\n".join(analyses),
            chunks_analyzed=analyzed,
            chunks_total=len(chunks),
            lines_submitted=len(events),
            lines_analyzed=lines_analyzed,
            lines_omitted_by_limits=omitted,
            lines_not_analyzed=len(scheduled) - lines_analyzed,
            lines_shortened=shortened,
            lines_considered=len(scheduled),
            lines_skipped_by_prefilter=skipped,
            model=effective_model,
            warnings=warnings,
        )

    async def test_connection(
        self,
        *,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> TestConnectionResponse:
        """One-shot connectivity check: builds the provider client and makes a
        single minimal call_chunk, reporting success/failure as a normal 200
        response rather than raising — this is a diagnostic, not an operation
        that should surface as a request error."""
        provider_cls = get_provider_class(provider)
        defaults = self._defaults[provider]
        effective_model = model or defaults.model
        effective_base_url = base_url or defaults.base_url

        try:
            instance = provider_cls(
                api_key=api_key,
                model=effective_model,
                base_url=effective_base_url,
                settings=self.settings,
            )
        except BadRequestError as e:
            return TestConnectionResponse(success=False, message=e.message, model=effective_model)

        test_event = LogEvent(
            source="cloudwatch",
            origin="connection-test",
            stream_or_key="connection-test",
            message="INFO connection test line",
            line_index=0,
        )
        prompt = build_prompt(
            [test_event],
            AnalysisContext(source_description="Connection test"),
            user_prompt="Reply with a brief confirmation that the connection works.",
        )
        try:
            await instance.call_chunk(SYSTEM_PROMPT, prompt)
        except LLMRateLimited as e:
            return TestConnectionResponse(
                success=False, message=f"Rate limited: {e}", model=effective_model
            )
        except (LLMQuotaExceededError, LLMRequestError) as e:
            return TestConnectionResponse(success=False, message=e.message, model=effective_model)
        except Exception as e:
            return TestConnectionResponse(success=False, message=str(e), model=effective_model)

        return TestConnectionResponse(
            success=True, message="Connected successfully.", model=effective_model
        )

    async def _reduce_analyses(
        self,
        analyses: list[str],
        provider: LLMProvider,
        max_retries: int,
    ) -> ChunkResult:
        prompt = build_reduction_prompt(analyses)
        for attempt in range(max_retries + 1):
            try:
                return await provider.call_chunk(REDUCTION_SYSTEM_PROMPT, prompt)
            except LLMRateLimited as e:
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt * 5)
                    continue
                raise LLMQuotaExceededError(str(e)) from e
            except (LLMQuotaExceededError, LLMRequestError):
                raise
            except Exception as e:
                raise LLMRequestError(str(e)) from e
        raise LLMRequestError('LLM reduction failed after retries')

    async def _call_chunk(
        self,
        chunk_events: list[LogEvent],
        context: AnalysisContext,
        provider: LLMProvider,
        max_retries: int,
        user_prompt: str | None = None,
        history: list[ChatMessage] | None = None,
    ) -> ChunkResult:
        prompt = build_prompt(chunk_events, context, user_prompt, history)
        for attempt in range(max_retries + 1):
            try:
                return await provider.call_chunk(SYSTEM_PROMPT, prompt)
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
