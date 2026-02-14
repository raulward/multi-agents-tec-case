from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from app.schemas.domain import Document

if TYPE_CHECKING:
    from app.rag.ingestion.fetcher import FetchResult
    from app.rag.ingestion.models import FetchOverrides, HtmlExtractSpec, SourceItem
    from app.rag.ingestion.parsers import ParsedMarkdown
    from app.schemas.domain import DocMetadata


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


class FetcherProtocol(Protocol):
    def fetch(self, url: str, fetch_overrides: "FetchOverrides") -> "FetchResult": ...


class PdfParserProtocol(Protocol):
    def parse(self, pdf_bytes: bytes, source_id: str) -> "ParsedMarkdown": ...


class HtmlParserProtocol(Protocol):
    def parse(self, html_text: str, extract_spec: "HtmlExtractSpec", source_id: str) -> "ParsedMarkdown": ...


class MarkdownEnricherProtocol(Protocol):
    def enrich(self, markdown: str) -> "DocMetadata": ...


class PipelineIngestorProtocol(Protocol):
    def parse(self, source: "SourceItem", payload: bytes) -> "ParsedMarkdown": ...

    def enrich(self, markdown: str) -> "DocMetadata": ...
