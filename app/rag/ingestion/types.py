from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.schemas.domain import Document


class SourceType(str, Enum):
    PDF = "pdf"
    HTML = "html"
    UNKNOWN = "unknown"


@dataclass
class IngestorOptions:
    chunk_size: int = 1200
    chunk_overlap: int = 200
    do_ocr: bool = False


class IngestorProtocol(Protocol):
    def ingest(self, source: str, options: IngestorOptions) -> Document: ...
