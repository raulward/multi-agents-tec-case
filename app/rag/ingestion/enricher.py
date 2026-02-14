from app.rag.metadata_enricher import MetadataEnricher
from app.schemas.domain import DocMetadata


class MarkdownEnricher:
    """Enriquecedor de metadados com LLM a partir de markdown."""

    def __init__(self, metadata_enricher: MetadataEnricher | None = None, max_chars: int = 1500) -> None:
        self._metadata_enricher = metadata_enricher or MetadataEnricher()
        self._max_chars = max_chars

    def enrich(self, markdown: str) -> DocMetadata:
        content = markdown[: self._max_chars]
        return self._metadata_enricher.enrich(content)


def enrich_markdown_with_llm(markdown: str) -> DocMetadata:
    """Wrapper de compatibilidade para enriquecimento legado."""
    return MarkdownEnricher().enrich(markdown)
