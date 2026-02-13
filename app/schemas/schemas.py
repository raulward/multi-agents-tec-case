from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Literal, Dict

import uuid

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User question")


class QueryResponse(BaseModel):
    answer: Optional[str] = None
    confidence: float = 0.0
    citations: List[Dict[str, Any]] = []
    extracted_metrics: Optional[Dict[str, Any]] = None
    sentiment_analysis: Optional[Dict[str, Any]] = None
    routing: Optional[Dict[str, Any]] = None
    trace: List[Dict[str, Any]] = []

class HealthResponse(BaseModel):
    status: str
    chunks_indexed: int
    model: str

class IngestResponse(BaseModel):
    documents_processed: int
    total_chunks: int


class HealthResponse(BaseModel):
    status: str
    chunks_indexed: int
    model: str

class IngestionRequest(BaseModel):
    urls: Optional[List[str]]


class Chunk(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any]

class Document(BaseModel):
    id: str
    company_name: str
    filename: str
    num_chunks: int
    text: str
    chunks: List[Chunk]
    metadata: dict[str, Any]

class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(description="Chunk id used as evidence")
    source: Optional[str] = Field(default=None, description="Document/file name")
    quote: Optional[str] = Field(default=None, description="Short supporting excerpt")


class RetrievalFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")  
    company_name: Optional[str] = None
    doc_type: Optional[str] = None


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    query: str = Field(description="The search query text")
    
    filter_company: Optional[str] = Field(
        default=None, 
        description="Filter by company name if explicitly mentioned always lower (e.g. 'apple', 'tesla')"
    )
    filter_doc_type: Literal[
        "Earnings Report",
        "Board Meeting Minutes",
        "Regulatory Filing",
        "Transcript",
        "Research Report",
    ] = Field(
        default=None, 
        description="Filter by document type (e.g. '10-K', 'Earnings Report')"
    )

class OrchestratorPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasoning: str
    search_queries: List[RetrievalQuery] = Field(
        description="List of targeted searches", 
        max_length=3, 
        min_length=1
    )
    target_agents: List[Literal["extractor", "sentiment", "qa"]] = Field(
        min_length=1, 
        max_length=3
    )
    complexity: Literal["simple", "medium", "complex"]

class FinancialMetrics(BaseModel):
    metric_name: str
    value: float
    unit: str
    period: str
    source: str
    context: Optional[str] = Field(default=None, description="Short context of source (1 phrase, optional)")

class ExtractionResult(BaseModel):
    company: str
    metrics: List[FinancialMetrics]
    summary: str = Field(description="Executive summary of 1-2 sentences about the findings.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=("Confidence in extraction (0-1).")
    )

class RiskItem(BaseModel):
    title: str = Field(description="Short risk title")
    description: str = Field(description="Brief explanation of the risk")
    severity: Literal["low", "medium", "high"] = Field(description="Estimated severity based only on context")
    citations: List[Citation] = Field(description="Supporting citations for this risk")

class HighlightItem(BaseModel):
    title: str = Field(description="Short positive highlight title")
    description: str = Field(description="Brief explanation of the highlight")
    citations: List[Citation] = Field(description="Supporting citations")

class RiskAssessment(BaseModel):
    sentiment: Literal["bullish", "bearish", "neutral"]
    key_risks: List[RiskItem]
    positive_highlights: List[HighlightItem]
    overall_rationale: str = Field(description="1-2 sentence justification for overall sentiment")
    confidence: float = Field(ge=0.0, le=1.0)

class QAAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    confidence: float = Field(ge=0.0, le=1.0, description="0-1: How grounded the response is")
    citations: List[Citation]
    reasoning: str = Field(description="CoT of your reasoning")