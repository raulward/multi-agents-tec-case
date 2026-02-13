from app.ai.agents.base import BaseAgent
from app.schemas.schemas import QAAnswer
from typing import Dict, Any, List

from app.ai.prompts.qa.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.qa.human_prompt import HUMAN_PROMPT

from app.ai.workflows.state import AgentState
from langchain_core.prompts import ChatPromptTemplate

class QAAgent(BaseAgent):
    def __init__(self, llm_client, name="qa"):
        super().__init__(llm_client, name)
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(QAAnswer)

    def execute(self, state: AgentState) -> Dict[str, Any]:
        query = state["query"]
        docs = state.get("retrieved_docs", [])

        if not docs:
            return {
                "answer": "Documents not found to provide an answer.",
                "reasoning": "No documents were provided for analysis.",
                "citations": [],
                "confidence": 0.0,
            }

        context = self._build_context(docs)

        human_prompt = HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | self.client_structured

        response: QAAnswer = chain.invoke({"query": query, "context": context})

        return {
            "answer": response.answer,
            "reasoning": response.reasoning,
            "citations": response.citations,
            "confidence": response.confidence
        }

        

    def _build_context(self, docs: List[dict]) -> str:
        chunks = []

        for i, doc in enumerate(docs[:5], 1):
            metadata = doc.get("metadata") or {}
            content = doc.get("content") or doc.get("text") or ""

            filename = metadata.get("filename") or metadata.get("source") or "Unknown"
            page = metadata.get("page", "?")
            chunk_id = metadata.get("chunk_id") or doc.get("chunk_id") or "unknown"

            chunks.append(
                f"[Chunk {i}]\n"
                f"chunk_id: {chunk_id}\n"
                f"source: {filename}\n"
                f"content:\n{content}\n"
            )

        return "\n---\n".join(chunks)