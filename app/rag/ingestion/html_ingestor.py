from app.rag.chunker import Chunker
from app.rag.ingestion.models import FetchOverrides, HtmlExtractSpec, SourceItem
from app.rag.ingestion.parsers import ParsedMarkdown
from app.schemas.domain import Document

from .types import FetcherProtocol, HtmlParserProtocol, IngestorOptions, MarkdownEnricherProtocol


class HtmlIngestor:
    """Ingestor de fontes HTML com parser e enricher injetados."""

    def __init__(
        self,
        parser: HtmlParserProtocol,
        enricher: MarkdownEnricherProtocol,
        fetcher: FetcherProtocol | None = None,
    ) -> None:
        self._parser = parser
        self._enricher = enricher
        self._fetcher = fetcher

    def parse(self, source: SourceItem, payload: bytes) -> ParsedMarkdown:
        if source.extract is None:
            raise ValueError("extract is required for html sources")
        html_text = payload.decode("utf-8", errors="ignore")
        return self._parser.parse(html_text, source.extract, source.id)

    def enrich(self, markdown: str):
        return self._enricher.enrich(markdown)

    def ingest(self, source: str, options: IngestorOptions) -> Document:
        if self._fetcher is None:
            raise RuntimeError("HtmlIngestor ingest() requires fetcher dependency")

        fetched = self._fetcher.fetch(source, FetchOverrides())
        parsed = self._parser.parse(
            fetched.content.decode("utf-8", errors="ignore"),
            HtmlExtractSpec(selectors=["body"]),
            source_id="html_doc_legacy",
        )
        enriched = self._enricher.enrich(parsed.markdown)

        metadata = dict(parsed.base_metadata)
        metadata.update(
            {
                "source_url": source,
                "resolved_url": fetched.resolved_url,
                "company_name": enriched.company_name.strip().lower(),
                "document_type": enriched.document_type,
                "document_date": enriched.document_date,
            }
        )

        chunker = Chunker(chunk_size=options.chunk_size, chunk_overlap=options.chunk_overlap)
        chunks = chunker.chunk(parsed.markdown, metadata)

        return Document(
            id=metadata.get("source_id", "html_doc_legacy"),
            company_name=metadata.get("company_name", "unknown"),
            num_chunks=len(chunks),
            text=parsed.markdown,
            chunks=chunks,
            metadata=metadata,
        )
