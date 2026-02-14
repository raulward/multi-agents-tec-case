from typing import List

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    source: str | None = None
    quote: str | None = None


class QAAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: List[Citation]
    reasoning: str = Field(
        description="Chain-of-thought reasoning"
    )
