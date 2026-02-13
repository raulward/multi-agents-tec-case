from pydantic import BaseModel, Field
from typing import Literal, List

DocumentType = Literal[
    "Earnings Report",
    "Board Meeting Minutes",
    "Regulatory Filing",
    "Transcript",
    "Research Report",
]

class DocMetadata(BaseModel):
    company_name: str = Field(..., description="Canonical company name")
    document_date: str = Field(..., description="Reporting period or document date (e.g., '4Q23', '2023', 'September 30, 2024')")
    document_type: DocumentType