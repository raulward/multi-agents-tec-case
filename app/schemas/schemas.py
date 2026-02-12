from pydantic import BaseModel, Field
from typing import List, Optional, Any

import uuid

class IngestionRequest(BaseModel):
    urls: Optional[List[str]]

class IngestionResponse(BaseModel):
    total_requested: int
    total_downloaded: int
    total_failed: int

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

