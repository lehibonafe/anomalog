import asyncio
import json
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
from app.services.llm.prompt_v6 import (
    REDUCTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_prompt,
    build_reduction_prompt,
)
from app.services.llm.registry import PROVIDERS, get_provider_class
from app.services.masking import mask_message


def _truncate_middle(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 5:
        return value[:max_chars]
    half = (max_chars - 5) // 2
    return value[:half] + " ... " + value[-half:]


def _trim_history(
    history: list[ChatMessage], token_budget: int
) -> tuple[list[ChatMessage], int, bool]:
    """Keep the newest complete turns within a conservative token budget."""
    if not history:
        return [], 0, False
    if token_budget <= 0:
        return [], len(history), False

    remaining = token_budget
    kept_reversed: list[ChatMessage] = []
    omitted = 0
    content_shortened = False
    for index in range(len(history) - 1, -1, -1):
        message = history[index]
        cost = log_filter.estimate_tokens(f"{message.role}: {message.content}") + 4
        if cost <= remaining:
            kept_reversed.append(message)
            remaining -= cost
            continue

        omitted = index + 1
        if not kept_reversed:
            max_chars = max(0, remaining * 3 - len(message.role) - 8)
            if max_chars:
                kept_reversed.append(
                    message.model_copy(
                        update={"content": _truncate_middle(message.content, max_chars)}
                    )
                )
                omitted -= 1
                content_shortened = True
        break

    kept_reversed.reverse()
    return kept_reversed, omitted, content_shortened


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
        history, history_messages_omitted, history_content_shortened = _trim_history(
            history, self.settings.max_chat_history_tokens
        )

        # Defense in depth: masking.py is applied when events are first fetched
        # from CloudWatch/CloudTrail, but this endpoint accepts a raw events
        # array from the client — re-mask here so a caller that bypasses the
        # normal fetch path can't leak unmasked secrets/PII to an LLM provider.
        # mask_message is idempotent, so this is a no-op for already-masked text.
        events = [e.model_copy(update={"message": mask_message(e.message)}) for e in events]
        events = log_filter.compact_json(events)
        derived_counts = log_filter.derived_counts(events)

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
            relevant, skipped = log_filter.select_for_question(
                events, user_prompt, self.settings
            )
        else:
            relevant, skipped = log_filter.select_relevant(events, self.settings)
        selected_count = len(relevant)
        compression = log_filter.compress_duplicates(relevant)
        original_lengths = {
            event.line_index: len(event.message) for event in compression.events
        }
        relevant = log_filter.truncate_and_cap(compression.events, self.settings)
        chunks = log_filter.chunk(relevant, self.settings)

        analyses: list[str] = []
        scheduled = [event for chunk_events in chunks for event in chunk_events]
        lines_considered = sum(
            compression.source_counts.get(event.line_index, 1) for event in scheduled
        )
        omitted = selected_count - lines_considered
        shortened = sum(
            len(event.message) < original_lengths[event.line_index] for event in scheduled
        )
        warnings: list[str] = []
        if history_messages_omitted or history_content_shortened:
            detail = f"{history_messages_omitted} older message(s) omitted"
            if history_content_shortened:
                detail += " and the newest oversized message was shortened"
            warnings.append(f"Conversation history was compacted: {detail}.")
        if compression.collapsed:
            warnings.append(
                f"Collapsed {compression.collapsed} repetitive log lines into counted "
                "representatives before analysis."
            )
        if omitted:
            warnings.append(f"Processing limits excluded {omitted} selected log lines.")
        if shortened:
            warnings.append(f"{shortened} scheduled log lines were shortened before analysis.")
        prompt_context = context.model_copy(
            update={
                "source_description": (
                    f"{context.source_description}; app_visible_logs={len(events)}; "
                    f"app_retrieval_excluded={skipped}; "
                    f"app_processing_omitted={omitted}; "
                    f"app_derived_counts={json.dumps(derived_counts, separators=(',', ':'))}"
                )
            }
        )
        analyzed = 0
        lines_analyzed = 0
        estimated_input_tokens = sum(
            log_filter.estimate_tokens(SYSTEM_PROMPT)
            + log_filter.estimate_tokens(
                build_prompt(chunk_events, prompt_context, user_prompt, history)
            )
            for chunk_events in chunks
        )
        for i, chunk_events in enumerate(chunks):
            await limiter.wait()
            try:
                result = await self._call_chunk(
                    chunk_events,
                    prompt_context,
                    instance,
                    defaults.max_retries,
                    user_prompt,
                    history,
                )
                analyses.append(result.analysis)
                analyzed += 1
                lines_analyzed += sum(
                    compression.source_counts.get(event.line_index, 1)
                    for event in chunk_events
                )
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
            consolidated = analyses[0].strip()
            if len(analyses) > 1:
                await limiter.wait()
                reduction_prompt = build_reduction_prompt(analyses, user_prompt)
                estimated_input_tokens += log_filter.estimate_tokens(
                    REDUCTION_SYSTEM_PROMPT
                ) + log_filter.estimate_tokens(reduction_prompt)
                try:
                    result = await self._reduce_analyses(
                        analyses, instance, defaults.max_retries, user_prompt
                    )
                    reduced = result.analysis.strip()
                    if reduced:
                        consolidated = reduced
                    else:
                        warnings.append(
                            "The consolidated answer was empty; showing the batch answers."
                        )
                        consolidated = "\n\n".join(
                            answer.strip() for answer in analyses if answer.strip()
                        )
                except (LLMQuotaExceededError, LLMRequestError) as e:
                    warnings.append(
                        "Could not consolidate all analyzed batches; showing the "
                        f"batch answers instead: {e.message}"
                    )
                    consolidated = "\n\n".join(
                        answer.strip() for answer in analyses if answer.strip()
                    )
            analyses = [consolidated] if consolidated else []

        return AnalysisResponse(
            analysis="\n\n".join(analyses),
            chunks_analyzed=analyzed,
            chunks_total=len(chunks),
            lines_submitted=len(events),
            lines_analyzed=lines_analyzed,
            lines_sent_to_model=len(scheduled),
            lines_collapsed_as_duplicates=compression.collapsed,
            lines_omitted_by_limits=omitted,
            lines_not_analyzed=lines_considered - lines_analyzed,
            lines_shortened=shortened,
            lines_considered=lines_considered,
            lines_skipped_by_prefilter=skipped,
            history_messages_omitted=history_messages_omitted,
            estimated_input_tokens=estimated_input_tokens,
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
        user_prompt: str | None = None,
    ) -> ChunkResult:
        prompt = build_reduction_prompt(analyses, user_prompt)
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
