from typing import Dict, Any
from langgraph import StateGraph, END
from langchain_openai import ChatOpenAI

from app.ai.workflows.state import AgentState
from app.ai.workflows.nodes import WorkflowNodes
from app.core.config import settings

class WorkflowManager:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=0.15,
            api_key=settings.OPENAI_API_KEY
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(AgentState)

        g.add_node("")
        g.add_node("")
        g.add_node("")
        g.add_node("")