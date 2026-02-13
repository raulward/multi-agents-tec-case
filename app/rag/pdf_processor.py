from pathlib import Path
from typing import List

from app.schemas.schemas import Document, Chunk

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from langchain_docling.loader import DoclingLoader, ExportType
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.rag.metadata_enricher import MetadataEnricher

from app.ai.structured_output import DocMetadata



import uuid

class PDFProcessor:

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.header_levels =  [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
        self._header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.header_levels)
        self._char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def parse_folder(self, folder: Path | str) -> List[Document]:
        parserd_docs = []
        for file in Path(folder).glob("*.pdf"):
            doc_parsed = self._parse(file)
            parserd_docs.append(doc_parsed)
        return parserd_docs

    def _parse(self, file: Path) -> Document:
        file = Path(file)
        md, base_meta = self._parse_pdf_to_markdown(file)
        
        doc_id = str(uuid.uuid4())

        enricher = MetadataEnricher()
        enriched: DocMetadata = enricher.enrich(md[:1500])

        doc_meta = {
            **base_meta,                  
            "doc_id": doc_id,
            "filename": file.name,
            "company_name": enriched.company_name.lower(),
            "document_date": enriched.document_date,
            "document_type": enriched.document_type,
        }

        print(doc_meta)

        chunks = self._chunk(md, doc_meta)

        return Document(
            id=doc_id,
            text=md,
            num_chunks=len(chunks),
            chunks=chunks,
            metadata=doc_meta,
            filename=file.name,
            company_name=enriched.company_name,
        )

    def _parse_pdf_to_markdown(self, file: Path) -> Tuple[str, Dict[str, Any]]:
        path = Path(file)
        loader = DoclingLoader(file_path=str(file), export_type=ExportType.MARKDOWN)
        docs = loader.load()

        md = "\n\n".join(d.page_content for d in docs).strip()

        meta: Dict[str, Any] = {}
        for d in docs:
            if d.metadata is not None:
                meta.update(d.metadata)

        meta.setdefault("source", str(path))

        return md, meta

    def _chunk(self, md: str, doc_meta: Dict[str, Any]) -> List[Chunk]:

        header_docs = self._header_splitter.split_text(md)

        chunks: List[Chunk] = []

        chunk_id = 0

        for hd in header_docs:
            block = (hd.page_content or "").strip()
            if not block:
                continue

            block_meta = dict(doc_meta)
            block_meta.update(hd.metadata or {})

            parts = self._char_splitter.split_text(block)
            total = len(parts)

            for i, part in enumerate(parts):
                part = part.strip()

                if not part:
                    continue

                chunk_meta = dict(block_meta)
                unique_chunk_id = str(uuid.uuid4())
                chunk_meta["chunk_id"] = unique_chunk_id
                chunk_meta["chunk_index_in_block"] = i
                chunk_meta["chunk_total_in_block"] = total
                chunk_meta["section_path"] = " > ".join(
                    [str(chunk_meta.get(level_key)).strip() for _, level_key in self.header_levels if chunk_meta.get(level_key)]
                )
                chunks.append(Chunk(id=unique_chunk_id, text=part, metadata=chunk_meta))
                chunk_id += 1

        return chunks


if __name__ == "__main__":
    pdf = "./data/processed/file_amazon.pdf"

    processor = PDFProcessor(chunk_size=1200, chunk_overlap=150)

    parsed = processor._parse(pdf)

    print("DOC METADATA:")
    print(parsed.metadata)
    print("\nN_CHUNKS:", len(parsed.chunks))

    for c in parsed.chunks[:2]:
        print("\n--- CHUNK ---")
        print("")
        print({k: c.metadata.get(k) for k in ["company", "filename", "chunk_id", "section_path", "h1", "h2", "h3", "chunk_index_in_block"]})
        print(c.text[:400], "...")
