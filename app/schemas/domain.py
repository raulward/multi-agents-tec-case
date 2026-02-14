from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


DocumentType = Literal[
    "Earnings Report",
    "Board Meeting Minutes",
    "Regulatory Filing",
    "Transcript",
    "Research Report",
]


class Chunk(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any]


class Document(BaseModel):
    id: str
    company_name: str
    num_chunks: int
    text: str
    chunks: List[Chunk]
    metadata: dict[str, Any]


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    score: float
    metadata: dict[str, Any]


class RetrievalFilters(BaseModel):
    company: Optional[str] = None
    doc_type: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[str] = None


class RetrievalQuery(BaseModel):
    query: str
    filters: Optional[RetrievalFilters] = None


class DocMetadata(BaseModel):
    company_name: str = Field(..., description="Canonical company name")
    document_date: str = Field(
        description="Reporting period or document date (e.g., '4Q23', '2023')",
    )
    document_type: DocumentType
