import traceback
import time
import json
from typing import Dict, Any, List

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
            raise

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
                    query_doc = query.get("filter_doc_type")

                    where_clause = {}
                    if query_company:
                        where_clause["company_name"] = query_company.lower()
                    if query_doc:
                        where_clause["document_type"] = query_doc 

                    response = self.rag.query(
                        query_text=query_text,
                        n_results=4,
                        where=where_clause if where_clause else None
                    )

                    if response and response.get("documents"):
                        docs = [
                            {"content": text, "metadata": meta}
                            for text, meta in zip(response["documents"][0], response["metadatas"][0])
                        ]
                        all_docs.extend(docs)

                all_docs = self._dedup_docs(all_docs)

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

    def run_agents(self, state: AgentState) -> AgentState:

        try:

            targets = state.get("selected_agents", []) 
            if not targets:
                targets = ["qa"]

            ALLOWED ={
                "extractor": {"extracted_metrics"},
                "sentiment": {"sentiment_analysis"},
                "qa": {"answer", "confidence", "citations", "reasoning"}
            }

            for agent_name in targets:
                agent = self.agent_registry.get(agent_name)
                
                if agent is None:

                    self._push_trace(
                            state,
                            step=f"agent:{agent_name}",
                            ok=False,
                            meta={},
                            err="agent_not_registered",
                        )
                    continue
                
                t0 = time.time()
                out = agent.execute(state)
                dt_ms = int((time.time() - t0) * 100)

                for action, value in out.items():
                    if action in ALLOWED.get(agent_name, set()):
                        state[action] = value
                    else:
                        self._push_trace(
                                state,
                                step=f"agent:{agent_name}:dropped_key",
                                ok=True,
                                meta={"key": action},
                        )

            if state.get("answer"):
                state["final_answer"] = state["answer"]
            elif state.get("sentiment_analysis"):
                state["final_answer"] = json.dumps(state["sentiment_analysis"], ensure_ascii=False)
            elif state.get("extracted_metrics"):
                state["final_answer"] = json.dumps(state["extracted_metrics"], ensure_ascii=False)

            return state

        
        except Exception as e:
            err = traceback.format_exc()
            self._push_trace(state, step="run_agents", ok=False, meta={}, err=err)
            raise
 
    def finalize(self, state: AgentState) -> AgentState:

        try:

            if state.get("confidence")  is None:
                state["confidence"] = 0.0
            if state.get("citations") is None:
                state["citations"] = []

            self._push_trace(
                state,
                step="finalize",
                ok=True,
                meta={"has_final_answer": bool(state.get("final_answer"))},
            )

            return state

        except Exception as e:
            err = traceback.format_exc()
            self._push_trace(state, step="finalize", ok=False, meta={}, err=err)
            raise

    def _push_trace(
        self,
        state: AgentState,
        step: str,
        ok: bool,
        meta: Dict[str, Any],
        err: str = None,
        plan: Dict = None,
    ) -> None:

        trace = state.get("agent_trace", [])
        event = {
            "ts_ms": int(time.time() * 1000),
            "step": step,
            "ok": ok,
            "meta": meta,
            "error": err,
        }
        if plan:
            event["plan"] = plan
        trace.append(event)
        state["agent_trace"] = trace

    def _get_last_plan(self, state: AgentState) -> Dict[str, Any]:

        for event in reversed(state.get("agent_trace", [])):
            if event.get("step") == "orchestrate" and event.get("plan"):
                return event["plan"]
        return {}

    def _dedup_docs(self, docs: List[dict]) -> List[dict]:

        seen = set()
        out = []
        for d in docs:
            md = d.get("metadata") or {}
            chunk_id = md.get("chunk_id") or d.get("chunk_id")
            content = d.get("content") or d.get("text") or ""
            source = md.get("source") or md.get("filename") or "unknown"
            
            
            key = chunk_id or (source, hash(content))
            
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
        
        return out