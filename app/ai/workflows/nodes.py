import traceback
import time
import json
from typing import Dict, Any, List

from app.ai.workflows.state import AgentState
from app.ai.agents.orchestrator import OrchestratorAgent
from app.rag.rag_processor import RAGProcessor


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

            state["search_queries"] = plan.get("search_queries", []) or []

            if not state["selected_agents"]:
                state["selected_agents"] = ["qa"]

            self._push_trace(
                state,
                step="orchestrate",
                ok=True,
                meta={
                    "selected_agents": state["selected_agents"],
                    "n_search_queries": len(state["search_queries"]),
                },
                plan=plan,
            )
            
            return state
        
        except Exception as e:
            err = traceback.format_exc()
            self._push_trace(state, step="orchestrate", ok=False, meta={}, err=err)
            raise
    
    def route_after_orchestrate(self, state: AgentState) -> str:
        search_queries = state.get("search_queries") or []
        if len(search_queries) > 0:
            return "retrieve"

        if state.get("selected_agents"):
            return "run_agents"

        return "finalize"

    def retrieve(self, state: AgentState) -> AgentState:

            try:

                search_queries = state.get("search_queries") or []

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
        targets = state.get("selected_agents", []) or []

        if not targets:
            self._push_trace(
                state,
                step="run_agents",
                ok=True,
                meta={"note": "no_targets"},
            )
            return state
        
        if "qa" not in targets:
            targets.append("qa")

        for agent_name in targets:
            agent = self.agent_registry.get(agent_name)
            if agent is None:
                self._push_trace(
                    state,
                    step=f"agent:{agent_name}",
                    ok=False,
                    meta={"returned_keys": [], "applied_keys": [], "dropped_keys": []},
                    err="agent_not_registered",
                )
                continue

            allowed_keys = getattr(agent, "produces", None)
            if not allowed_keys:
                self._push_trace(
                    state,
                    step=f"agent:{agent_name}",
                    ok=False,
                    meta={"returned_keys": [], "applied_keys": [], "dropped_keys": []},
                    err="agent_missing_produces",
                )
                continue

            t0 = time.time()
            out = None

            try:
                out = agent.execute(state)
                if not isinstance(out, dict):
                    raise TypeError(f"agent_output_not_dict: {type(out).__name__}")

                returned_keys = list(out.keys())
                applied_keys: List[str] = []
                dropped_keys: List[str] = []

                for k, v in out.items():
                    if k in allowed_keys:
                        state[k] = v
                        applied_keys.append(k)
                    else:
                        dropped_keys.append(k)

                dt_ms = int((time.time() - t0) * 1000)

                self._push_trace(
                    state,
                    step=f"agent:{agent_name}",
                    ok=True,
                    meta={
                        "dt_ms": dt_ms,
                        "returned_keys": returned_keys,
                        "applied_keys": applied_keys,
                        "dropped_keys": dropped_keys,
                    },
                )

            except Exception:
                dt_ms = int((time.time() - t0) * 1000)
                err = traceback.format_exc()

                self._push_trace(
                    state,
                    step=f"agent:{agent_name}",
                    ok=False,
                    meta={
                        "dt_ms": dt_ms,
                        "returned_keys": list(out.keys()) if isinstance(out, dict) else [],
                        "applied_keys": [],
                        "dropped_keys": [],
                    },
                    err=err,
                )
                continue

        return state

    def finalize(self, state: AgentState) -> AgentState:
        try:
            
            if state.get("confidence") is None:
                state["confidence"] = 0.0
            if state.get("citations") is None:
                state["citations"] = []

            state["final_answer"] = self._compose_final_answer(state)
        
            self._push_trace(
                state,
                step="finalize",
                ok=True,
                meta={"has_final_answer": bool(state.get("final_answer"))},
            )
            return state

        except Exception:
            err = traceback.format_exc()
            self._push_trace(state, step="finalize", ok=False, meta={}, err=err)
            raise
    
    def _compose_final_answer(self, state: AgentState) -> str:

        if state.get("answer"):
            return state["answer"]
        if state.get("extracted_metrics"):
            return json.dumps(state["extracted_metrics"], ensure_ascii=False)
        if state.get("sentiment_analysis"):
            return json.dumps(state["sentiment_analysis"], ensure_ascii=False)

        return "Baseado nos documentos fornecidos, não encontrei evidências suficientes para responder."


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