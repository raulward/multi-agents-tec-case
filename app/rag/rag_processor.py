from typing import Any, Dict, Optional, Set

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions

from app.core.config import settings
from app.schemas.domain import Chunk


class RAGProcessor:

    def __init__(self, persist_directory: str, collection_name: str):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.fe_openai = embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.OPENAI_API_KEY,
            model_name="text-embedding-3-small"
        )
        self.collection: Collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.fe_openai,
            metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, chunks: list[Chunk]) -> None:

        self.collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks]
        )

    def query(self, query_text: str, n_results: int = 3, where: Optional[Dict[str, Any]] = None):
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=self._build_where(where)
        )

    def _build_where(self, where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        if where is None:
            return None

        if not isinstance(where, dict):
            raise TypeError(f"where must be dict or None, got {type(where)}")
        if any(k.startswith("$") for k in where.keys()):
            return where
        cleaned: Dict[str, Any] = {}
        for k, v in where.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip().lower() in {"", "null", "none"}:
                continue
            cleaned[k] = v
        if not cleaned:
            return None
        if len(cleaned) == 1:
            return cleaned
        return {"$and": [{k: v} for k, v in cleaned.items()]}

    def list_distinct_company_names(self, limit: int = 5000) -> list[str]:
        data = self.collection.get(
            include=["metadatas"],
            limit=limit,
        )
        metas = data.get("metadatas") or []
        companies: Set[str] = set()
        for md in metas:
            if not md:
                continue
            c = md.get("company_name")
            if isinstance(c, str) and c.strip():
                companies.add(c.strip().lower())
        return sorted(companies)
