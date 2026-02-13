import chromadb
from chromadb.api.models.Collection import Collection

from app.schemas.schemas import Chunk

from chromadb.utils import embedding_functions

from typing import List, Optional, Any, Dict, Set

from app.core.config import settings

from app.rag.pdf_processor import PDFProcessor


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

    def upsert(self, chunks: List[Chunk]) -> None:

        self.collection.upsert(
            ids = [c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks]
        )

    def query(self, query_text: str, n_results: int = 3, where: Optional[Dict[str, Any]] = None):
        print(f"🔍 Buscando por: '{query_text}'")
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
        # Chroma não tem DISTINCT; então pegamos metadatas e fazemos set()
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

if __name__ == "__main__":
    DB_PATH = "./chroma_db_test"
    COLLECTION_NAME = "test_collection"
    pdf = "./data/processed/"
    
    try:

        processor = RAGProcessor(persist_directory=DB_PATH, collection_name=COLLECTION_NAME)

        # pdf_processor = PDFProcessor(chunk_size=1200, chunk_overlap=150)

        # docs = pdf_processor.parse_folder(pdf)

        # for doc in docs:
        #     processor.upsert(doc.chunks)

        print("Total indexed chunks:", processor.collection.count())


        results = processor.query(
            "Qual foi a receita da Apple no Q4 2024 e como se compara com o Q4 2023?",
            n_results=5,
            where={"company_name": "apple"},
        )

        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        dists = results.get("distances", [])

        if docs and len(docs) > 0 and len(docs[0]) > 0:
            print(f"Texto Encontrado: {docs[0][0]}")
            print(f"Metadata: {metas[0][0]}")
            print(f"Distância (Cosseno): {dists[0][0]}")
        else:
            print("❌ Nenhum resultado encontrado.")

    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        print("Dica: Verifique se a variável de ambiente OPENAI_API_KEY está configurada.")