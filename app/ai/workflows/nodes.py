from typing import Dict, Any, List
import traceback
import time

from app.ai.workflows.state import AgentState
from app.ai.agents.orchestrator import OrchestratorAgent
from app.rag.rag_processor import RAGProcessor

from app.schemas.schemas import RetrievalQuery

class WorkflowNodes:

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        rag_processor: RAGProcessor,
        agent_registry: Dict[str, Any],
    ):
        self.orchestrator = orchestrator
        self.rag = rag_processor
        self.agent_registry = agent_registry

    def orchestrate(self, state: AgentState) -> AgentState:

        try:
            plan = self.orchestrator.execute(state)

            state["selected_agents"] = plan.get("target_agents", [])
            state["routing_reasoning"] = plan.get("reasoning", "")

            if not state["selected_agents"]:
                state["selected_agents"] = ["qa"]

            self._push_trace(
                state,
                step="orchestrate",
                ok=True,
                meta={
                    "selected_agents": state["selected_agents"],
                    "n_search_queries": len(plan.get("search_queries", [])),
                },
                plan=plan, 
            )
            
            return state
        except Exception as e:

            err = traceback.format_exc()
            self._push_trace(state, step="orchestrate", ok=False, meta={}, err=err)

    def retrieve(self, state: AgentState) -> AgentState:

            try:

                last_plan = self._get_last_plan(state)
                search_queries = last_plan.get("search_queries", []) if last_plan else []

                if not search_queries:
                    search_queries = [RetrievalQuery(query=state["query"])]

                all_docs: List[dict] = []

                for query in search_queries:

                    query_text = query.get("query")
                    query_company = query.get("filter_company")
                    query_doc = query.get("filter_document_type")

                    where_clause = {}

                    where_clause["company_name"] = query_company.lower() if query_company else ""
                    where_clause["document_type"] = query_company.lower() if query_company else "" 

                    response = self.rag.query(
                        query_text=query_text,
                        n_results=4,
                        where=where_clause
                    )

                    if response and response.get("documents"):
                        docs = [
                            {"content": text, "metadata": meta}
                            for text, meta in zip(response["documents"][0], response["metadata"][0])
                        ]
                        all_docs.extend(docs)

                all_docs = self._dedup(all_docs)

                state["retrieved_docs"] = all_docs

                self._push_trace(
                    state,
                    step="retrieve",
                    ok=True,
                    meta={
                        "retrieved_count": len(all_docs),
                        "queries_executed": len(search_queries),
                    }
                )

                return state
            
            except Exception as e:
                err = traceback.format_exc()
                self._push_trace(state, step="retrieve", ok=False, meta={}, err=err)
                raise