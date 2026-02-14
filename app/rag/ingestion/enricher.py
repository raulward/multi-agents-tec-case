from app.rag.metadata_enricher import MetadataEnricher
from app.schemas.domain import DocMetadata


def enrich_markdown_with_llm(markdown: str) -> DocMetadata:
    content = markdown[:1500]
    return MetadataEnricher().enrich(content)
