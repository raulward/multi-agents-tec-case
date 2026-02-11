import chromadb
from chromadb.api.models.Collection import Collection

from app.schemas.schemas import Chunk

from typing import List


class RAGProcessor:

    def __init__(self, persist_directory: str, collection_name: str):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection: Collection = self.client.get_or_create_collection(
            collection_name=collection_name,
        )

    def upsert(self, chunks: List[Chunk], e) ->
