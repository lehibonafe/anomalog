from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # AWS
    aws_profile: str | None = None
    aws_region: str = "ap-southeast-1"

    # LiteLLM (default provider — team's internal proxy)
    litellm_api_key: str
    litellm_model: str = "qwen3:4b"
    litellm_base_url: str = "http://llm.etapinc.com/v1"

    # Gemini (opt-in; no longer the server-configured default)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_rpm_limit: int = 8
    gemini_max_chunks_per_analysis: int = 6
    gemini_max_retries: int = 2

    # Masking service (external PII masking API — primary masker; falls back
    # to local mask_message on failure)
    masking_service_url: str | None = "https://pii.etapinc.com"
    masking_service_api_key: str | None = None  # unset => external masking disabled, local-only
    masking_service_mode: str = "pipeline"  # required by /api/mask/structured/; "pipeline" vs "webchat" just categorizes the session server-side
    masking_service_timeout_s: float = 5.0
    masking_service_verify_ssl: bool = False  # pii.etapinc.com has a self-signed cert today; set True once a trusted cert is issued
    masking_service_batch_size: int = 200

    # Log volume caps
    max_time_range_days: int = 7
    max_log_search_lines: int = 5000
    max_chat_history_messages: int = 40
    max_analysis_lines: int = 1500
    max_analysis_chars: int = 500_000
    max_line_length: int = 2000
    chunk_size_lines: int = 250

    cors_origins: list[str] = ["http://localhost:5173"]

    # Inbound API abuse guard (per-client-IP, per-process — see InboundRateLimiter)
    inbound_rate_limit_per_minute: int = 120

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
