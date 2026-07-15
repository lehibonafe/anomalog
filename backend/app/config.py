from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # AWS
    aws_profile: str | None = None
    aws_region: str = "ap-southeast-1"

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    gemini_rpm_limit: int = 8
    gemini_max_chunks_per_analysis: int = 6
    gemini_max_retries: int = 2

    # Log volume caps
    max_time_range_days: int = 7
    max_log_search_lines: int = 5000
    max_analysis_lines: int = 1500
    max_analysis_chars: int = 500_000
    max_line_length: int = 2000
    chunk_size_lines: int = 250

    # S3
    max_s3_object_bytes: int = 2_000_000
    max_s3_total_bytes: int = 5_000_000

    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
