from typing import Dict, Optional, get_args
from langchain_openai import ChatOpenAI

from app.ai.agents.orchestrator import OrchestratorAgent
from app.ai.agents.extractor import ExtractorAgent
from app.ai.agents.qa import QAAgent
from app.ai.agents.sentiment import SentimentAgent
from app.schemas.domain import DocumentType
from app.rag.rag_processor import RAGProcessor
from app.rag.rag_service import RagService
from app.core.config import settings


class WorkflowDependencies:

    _instance: Optional['WorkflowDependencies'] = None

    def __init__(self, client: ChatOpenAI):
        self.client = client or ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )
        rag_processor = RAGProcessor(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION
        )
        self.rag = RagService(rag_processor)
        self.doc_types = list(get_args(DocumentType))
        self.company_catalog = self.rag.list_distinct_company_names()

        self.orchestrator = OrchestratorAgent(
            llm_client=self.client,
            name="orchestrator",
            company_catalog=self.company_catalog,
            doc_types=self.doc_types,
        )
        self.extractor = ExtractorAgent(llm_client=self.client, name="extractor")
        self.sentiment = SentimentAgent(llm_client=self.client, name="sentiment")
        self.qa = QAAgent(llm_client=self.client, name="qa")
        
        self.agent_registry: Dict[str, any] = {
            "extractor": self.extractor,
            "sentiment": self.sentiment,
            "qa": self.qa,
        }

    @classmethod
    def get_instance(cls, client: Optional[ChatOpenAI] = None) -> 'WorkflowDependencies':
        if cls._instance is None:
            cls._instance = cls(client)
        return cls._instance    
    
    @classmethod
    def reset(cls):
        """Reset singleton (useful for testing)"""
        cls._instance = None
