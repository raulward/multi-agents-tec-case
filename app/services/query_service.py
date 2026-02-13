from typing import Any, Dict, Optional, List

from app.ai.workflows.workflow import create_initial_state
from app.schemas.schemas import QueryResponse


class QueryService:
    def __init__(self, workflow_app, deps):
        self.workflow_app = workflow_app
        self.deps = deps

    def run(self, query: str) -> QueryResponse:
        initial_state = create_initial_state(query, company_catalog=self.deps.company_catalog)

        final_state: Optional[Dict[str, Any]] = None
        for event in self.workflow_app.stream(initial_state):
            for _, st in event.items():
                final_state = st

        if final_state is None:
            raise RuntimeError("Workflow produced no output")

        raw_citations = final_state.get("citations") or []
        citations = self._parse_citations(raw_citations)

        resp = self._build_query_response(final_state, citations)

        return resp
    
    def _parse_citations(self, raw_citations: List) -> List[Dict[str, Any]]:
         return [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in raw_citations
        ]
    
    def _build_query_response(self, final_state: Dict[str, Any], citations: List[Dict[str, Any]]):
        return QueryResponse(
            final_answer=final_state.get("final_answer"),
            confidence=float(final_state.get("confidence", 0.0) or 0.0),
            citations=citations,
            extracted_metrics=final_state.get("extracted_metrics"),
            sentiment_analysis=final_state.get("sentiment_analysis"),
            routing={
                "selected_agents": final_state.get("selected_agents", []),
                "reasoning": final_state.get("routing_reasoning", ""),
            },
            trace=final_state.get("agent_trace", []),
        )