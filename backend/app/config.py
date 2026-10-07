from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # AWS
    aws_profile: str | None = None
    aws_region: str = "ap-southeast-1"
    aws_role_arn: str | None = None
    aws_role_external_id: str | None = None
    aws_role_session_name: str = "anomalog"
    aws_include_linked_accounts: bool = False
    # Comma-separated names or ARNs for centralized CloudTrail CloudWatch Logs
    # groups. When set, the CloudTrail tab searches these instead of the
    # monitoring account's regional CloudTrail event history.
    cloudtrail_log_group_identifiers: str | None = None

    # LiteLLM (default provider — team's internal proxy)
    litellm_api_key: str
    litellm_model: str = "qwen3.8-flash"
    litellm_base_url: str = "http://llm.etapinc.com/v1"
    litellm_enable_thinking: bool = False
    # Additional destinations explicitly trusted for each provider.
    model_base_url_allowlist: dict[
        Literal["litellm", "openai", "anthropic", "ollama"], list[str]
    ] = Field(default_factory=dict)

    # Gemini (opt-in; no longer the server-configured default)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_rpm_limit: int = 8
    gemini_max_chunks_per_analysis: int = 6
    gemini_max_retries: int = 2
    gemini_thinking_level: Literal["low", "medium", "high"] = "low"
    # Retained for callers that explicitly select a Gemini 2.5 model.
    gemini_thinking_budget: int = Field(default=0, ge=-1, le=24576)

    # Masking service (external PII masking API — primary masker; falls back
    # to local mask_message on failure)
    masking_service_url: str | None = "https://pii.etapinc.com"
    masking_service_api_key: str | None = None  # unset => external masking disabled, local-only
    masking_service_mode: str = "pipeline"  # required by /api/mask/structured/; "pipeline" vs "webchat" just categorizes the session server-side
    masking_service_timeout_s: float = 5.0
    masking_service_verify_ssl: bool = False  # pii.etapinc.com has a self-signed cert today; set True once a trusted cert is issued
    masking_service_batch_size: int = 200

    # CloudWatch Logs Live Tail safety and cost controls
    live_tail_max_concurrent_sessions: int = Field(default=3, ge=1)
    live_tail_inactivity_timeout_seconds: int = Field(default=900, ge=900, le=1800)
    live_tail_cost_per_minute_usd: float = Field(default=0.01, ge=0)
    live_tail_free_tier_minutes: int = Field(default=1800, ge=0)

    # Log volume caps
    max_time_range_days: int = 7
    max_log_search_lines: int = 5000
    max_chat_history_messages: int = 40
    max_chat_history_tokens: int = Field(default=4000, ge=0)
    max_analysis_lines: int = 1500
    max_analysis_chars: int = 500_000
    max_analysis_tokens: int = Field(default=40_000, ge=1000)
    max_llm_output_tokens: int = Field(default=2048, ge=256, le=8192)
    max_line_length: int = 2000
    chunk_size_lines: int = 250

    cors_origins: list[str] = ["http://localhost:5173"]

    # Inbound API abuse guard (per-client-IP, per-process — see InboundRateLimiter)
    inbound_rate_limit_per_minute: int = 120

    @field_validator("litellm_base_url")
    @classmethod
    def validate_litellm_base_url(cls, value: str) -> str:
        return cls._validate_model_url(value)

    @field_validator("model_base_url_allowlist")
    @classmethod
    def validate_model_base_url_allowlist(cls, value: dict) -> dict:
        for urls in value.values():
            for url in urls:
                cls._validate_model_url(url)
        return value

    @staticmethod
    def _validate_model_url(value: str) -> str:
        parsed = urlsplit(value)
        if (
            value != value.strip()
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Model base URLs must be HTTP(S) URLs without credentials, query, or fragment")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("Model base URL has an invalid port") from exc
        return value

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
