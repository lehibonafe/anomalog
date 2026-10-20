from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import AnalysisResponse


class InvestigationTurn(BaseModel):
    id: int = Field(ge=0)
    question: str = Field(min_length=1, max_length=1000)
    response: AnalysisResponse


class InvestigationWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(min_length=1, max_length=100)
    start_time: str = Field(default="", alias="startTime", max_length=64)
    end_time: str = Field(default="", alias="endTime", max_length=64)
    turns: list[InvestigationTurn] = Field(min_length=1, max_length=100)


class SavedInvestigation(InvestigationWrite):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    updated_at: datetime = Field(alias="updatedAt")


class InvestigationListResponse(BaseModel):
    items: list[SavedInvestigation]
    next_offset: int | None = None


class InvestigationImportRequest(BaseModel):
    items: list[SavedInvestigation] = Field(max_length=20)


class InvestigationImportResponse(BaseModel):
    imported: int
