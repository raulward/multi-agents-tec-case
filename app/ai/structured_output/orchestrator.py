from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import DocumentType


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="The search query text")
    filter_company: Optional[str] = Field(
        default=None,
        description="Filter by company name if explicitly mentioned in canonical form"
    )
    filter_doc_type: Optional[DocumentType] = None


class OrchestratorPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasoning: str
    search_queries: List[RetrievalQuery] = Field(
        description="List of targeted searches",
        max_length=5
    )
    target_agents: List[Literal["extractor", "sentiment"]] = Field(
        max_length=2
    )
    complexity: Literal["simple", "medium", "complex"]
