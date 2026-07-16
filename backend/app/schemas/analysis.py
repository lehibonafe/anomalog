from typing import Literal

from pydantic import BaseModel

from app.schemas.common import LogEvent


class AnalysisContext(BaseModel):
    source_description: str


class AnalysisRequest(BaseModel):
    events: list[LogEvent]
    context: AnalysisContext
    provider: Literal["gemini", "openai", "anthropic", "ollama"] = "gemini"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    user_prompt: str | None = None


class TestConnectionRequest(BaseModel):
    provider: Literal["gemini", "openai", "anthropic", "ollama"] = "gemini"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    model: str


class Finding(BaseModel):
    id: str
    severity: Literal["critical", "warning", "info"]
    category: Literal["error", "stack_trace", "anomaly", "pattern"]
    line_index_start: int
    line_index_end: int
    excerpt: str
    explanation: str


class ChunkResult(BaseModel):
    findings: list[Finding]


class AnalysisResponse(BaseModel):
    findings: list[Finding]
    chunks_analyzed: int
    chunks_total: int
    lines_considered: int
    lines_skipped_by_prefilter: int
    model: str
    warnings: list[str] = []
