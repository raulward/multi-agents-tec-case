import uuid
from typing import Any, Dict, List

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.schemas.domain import Chunk


class Chunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.header_levels = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
        self._header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.header_levels)
        self._char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def chunk(self, md: str, doc_meta: Dict[str, Any]) -> List[Chunk]:
        header_docs = self._header_splitter.split_text(md)
        chunks: List[Chunk] = []

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

        return chunks
