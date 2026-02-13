from app.ai.agents.base import BaseAgent
from app.schemas.schemas import FinancialMetrics
from typing import Dict, Any, List
import json

from app.ai.prompts.extractor.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.extractor.human_prompt import HUMAN_PROMPT

from app.ai.workflows.state import AgentState

from app.schemas.schemas import ExtractionResult
from langchain_core.prompts import ChatPromptTemplate

class ExtractorAgent(BaseAgent):

    produces = {"extracted_metrics"}

    def __init__(self, llm_client, name="extractor"):
        super().__init__(llm_client, name)
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(ExtractionResult)

    def execute(self, state: AgentState) -> Dict[str, Any]:
        query = state["query"]
        docs = state.get("retrieved_docs", [])

        if not docs:
            return {
                "extracted_metrics": ExtractionResult(
                    company="Unknown",
                    metrics=[],
                    summary="No documents provided for extraction.",
                    confidence=0.0
                ).model_dump(),
            }
    
        context = self._build_context(docs)

        human_prompt = HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | self.client_structured

        extracts: ExtractionResult = chain.invoke({
            "query": query,
            "context": context
        })

        return {
            "extracted_metrics": extracts.model_dump(),
        }
