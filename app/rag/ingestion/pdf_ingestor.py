"""Legacy module: unused by the deterministic /ingest pipeline."""

import tempfile
from pathlib import Path

import requests

from app.rag.chunker import Chunker
from app.rag.pdf_processor import PDFProcessor
from app.schemas.domain import Document

from .types import IngestorOptions


class PdfIngestor:
    def ingest(self, source: str, options: IngestorOptions) -> Document:
        response = requests.get(source)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)

        processor = PDFProcessor()
        parsed = processor.extract(tmp_path)

        chunker = Chunker(
            chunk_size=options.chunk_size,
            chunk_overlap=options.chunk_overlap,
        )
        chunks = chunker.chunk(parsed["text"], parsed["metadata"])

        return Document(
            id=parsed["id"],
            company_name=parsed["company_name"],
            num_chunks=len(chunks),
            text=parsed["text"],
            chunks=chunks,
            metadata=parsed["metadata"],
        )
