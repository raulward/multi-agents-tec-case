from app.schemas.schemas import OrchestratorPlan 
from .base import BaseAgent

from app.ai.prompts.orchestrator.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.orchestrator.human_prompt import HUMAN_PROMPT

from langchain_core.prompts import ChatPromptTemplate

from app.ai.workflows.state import AgentState


class OrchestratorAgent(BaseAgent):

    def __init__(self, llm_client, name):
        super().__init__(llm_client, name="orchestrator")
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(OrchestratorPlan)

    def execute(self, state: AgentState):
        query = state['query']

        human_prompt = HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", human_prompt),
        ])

        catalog = state.get("company_catalog", [])
        plan = (prompt | self.client_structured).invoke({"query": query, "catalog": catalog})

        
        search_queries = [q.model_dump() for q in plan.search_queries]

        return {
            "search_queries": search_queries,
            "target_agents": plan.target_agents,
            "reasoning": plan.reasoning
        }