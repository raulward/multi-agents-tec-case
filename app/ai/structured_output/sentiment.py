from typing import List, Literal

from pydantic import BaseModel, Field

from .qa import Citation


class RiskItem(BaseModel):
    title: str
    description: str
    severity: Literal["low", "medium", "high"]
    citations: List[Citation]


class HighlightItem(BaseModel):
    title: str
    description: str
    citations: List[Citation]


class RiskAssessment(BaseModel):
    sentiment: Literal["hawkish", "dovish", "neutral", "bullish", "bearish"]
    key_risks: List[RiskItem]
    positive_highlights: List[HighlightItem]
    overall_rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
