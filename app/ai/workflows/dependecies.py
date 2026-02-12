from typing import Dict, Optional
from langchain_openai import ChatOpenAI

from app.ai.agents.orchestrator import OrchestratorAgent
from app.ai.agents.extractor import ExtractorAgent
from app.ai.agents.qa import QAAgent
from app.ai.agents.sentiment import SentimentAgent
from app.rag.rag_processor import RAGProcessor
from app.core.config import settings


class WorkflowDependencies:

    _instance: Optional['WorkflowDependencies'] = None

    def __init__(self, client: ChatOpenAI):
        self.client = client
        self.rag = RAGProcessor(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION
        )

        self.orchestrator = OrchestratorAgent(llm_client=client, name="orchestrator")
        self.extractor = ExtractorAgent(llm_client=client, name="extractor")
        self.sentiment = SentimentAgent(llm_client=client, name="sentiment")
        self.qa = QAAgent(llm_client=client, name="qa")
        
        self.agent_registry: Dict[str, any] = {
            "extractor": self.extractor,
            "sentiment": self.sentiment,
            "qa": self.qa,
        }

    def get_instance(cls, client: Optional[ChatOpenAI] = None) -> 'WorkflowDependencies':
        """Get or create singleton instance"""
        if cls._instance is None:
            if client is None:
                raise ValueError("LLM must be provided on first initialization")
            cls._instance = cls(client)
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset singleton (useful for testing)"""
        cls._instance = None