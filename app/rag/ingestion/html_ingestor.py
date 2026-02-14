"""Legacy module: unused by the deterministic /ingest pipeline."""

import requests
from bs4 import BeautifulSoup

from app.schemas.domain import Chunk, Document

from .types import IngestorOptions


class HtmlIngestor:
    
    def ingest(self, source: str, options: IngestorOptions) -> Document:
        response = requests.get(source)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator="\n")

        chunk = Chunk(
            id="html_chunk_1",
            text=text,
            metadata={"source": source},
        )

        return Document(
            id="html_doc_1",
            company_name="unknown",
            num_chunks=1,
            text=text,
            chunks=[chunk],
            metadata={"source": source},
        )
