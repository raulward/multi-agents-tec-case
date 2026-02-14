from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.rag.ingestion.models import IngestFailure, SourceItem

class HealthResponse(BaseModel):
    status: str
    chunks_indexed: int
    model: str


class IngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: Optional[List[SourceItem]] = None


class IngestResponse(BaseModel):
    total_requested: int
    total_downloaded: int
    total_failed: int
    failures: List[IngestFailure] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    final_answer: Optional[str]
    confidence: float
    citations: list
    extracted_metrics: Optional[dict]
    sentiment_analysis: Optional[dict]
    routing: dict
    trace: List[dict]
