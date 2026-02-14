from pydantic import BaseModel, Field
from typing import List, Optional


class FinancialMetrics(BaseModel):
    metric_name: str
    value: float
    unit: str
    period: str
    source: str
    context: Optional[str] = Field(
        default=None,
        description="Short context of source (optional)"
    )


class ExtractionResult(BaseModel):
    company: str
    metrics: List[FinancialMetrics]
    summary: str = Field(
        description="Executive summary of 1-2 sentences."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in extraction (0-1)"
    )