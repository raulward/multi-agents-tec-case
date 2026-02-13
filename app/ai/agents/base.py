from abc import ABC, abstractmethod
from typing import Any, Dict, Set
import time


class BaseAgent(ABC):

    produces: Set[str] = set()

    def __init__(self, llm_client, name: str):
        
        self.client = llm_client
        self.name = name

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        #TODO -> Tracing
        pass

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Lógica específica do agente - implementar nas subclasses"""
        pass

        
    def _build_context(self, docs: list[dict], extra_metadata_keys: list[str] | None = None) -> str:
        chunks = []
        keys = extra_metadata_keys or []
        for i, doc in enumerate(docs[:5], 1):
            metadata = doc.get("metadata") or {}
            content = (doc.get("content") or doc.get("text") or "").strip()
            if not content:
                continue
            header_parts = [f"source={metadata.get('filename', 'Unknown')}"]
            for key in keys:
                if val := metadata.get(key):
                    header_parts.append(f"{key}={val}")
            chunk_id = metadata.get("chunk_id", "unknown")
            chunks.append(f"[Chunk {i}]\nchunk_id: {chunk_id}\n{' | '.join(header_parts)}\ncontent:\n{content}\n")
        return "\n---\n".join(chunks)

