from typing import Literal

from pydantic import BaseModel

from app.schemas.common import LogEvent


class AnalysisContext(BaseModel):
    source_description: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AnalysisRequest(BaseModel):
    events: list[LogEvent]
    context: AnalysisContext
    provider: Literal["gemini", "openai", "anthropic", "ollama", "litellm"] = "litellm"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    user_prompt: str | None = None
    history: list[ChatMessage] = []


class TestConnectionRequest(BaseModel):
    provider: Literal["gemini", "openai", "anthropic", "ollama", "litellm"] = "litellm"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    model: str


class ChunkResult(BaseModel):
    analysis: str


class LineReference(BaseModel):
    start: int
    end: int


class AnalysisResponse(BaseModel):
    analysis: str
    references: list[LineReference] = []
    chunks_analyzed: int
    chunks_total: int
    lines_submitted: int = 0
    lines_analyzed: int = 0
    lines_sent_to_model: int = 0
    lines_collapsed_as_duplicates: int = 0
    lines_omitted_by_limits: int = 0
    lines_not_analyzed: int = 0
    lines_shortened: int = 0
    lines_considered: int
    lines_skipped_by_prefilter: int
    history_messages_omitted: int = 0
    estimated_input_tokens: int = 0
    model: str
    warnings: list[str] = []
