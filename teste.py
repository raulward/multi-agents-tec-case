# %% LANGGRAPH (1 célula) — usando AgentState + OrchestratorAgent do seu projeto
# Premissas:
# - Você já indexou (Chroma persistido).
# - OPENAI_API_KEY está definido no ambiente.
# - Este workflow usa: OrchestratorAgent -> Retrieval -> (extractor/sentiment/qa) em ordem.
# - Mostra as fases via app.stream().

import os, time, json, traceback
from typing import Any, Dict, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

import importlib
import app.rag.rag_processor as rp

importlib.reload(rp)

from app.rag.rag_processor import RAGProcessor

from app.ai.workflows.state import AgentState

import app.ai.agents.orchestrator as orch_mod
import app.ai.agents.extractor as ext_mod
import app.ai.agents.qa as qa_mod
import app.ai.agents.sentiment as sent_mod

importlib.reload(orch_mod)
importlib.reload(ext_mod)
importlib.reload(qa_mod)
importlib.reload(sent_mod)

from app.ai.agents.orchestrator import OrchestratorAgent
from app.ai.agents.extractor import ExtractorAgent
from app.ai.agents.qa import QAAgent
from app.ai.agents.sentiment import SentimentAgent

from app.core.config import settings
# ---------------- CONFIG ----------------
PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db_test")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "test_collection")

QUERY = "Qual foi a receita da Apple no Q4 2024 e como se compara com o Q4 2023?"
DEFAULT_TOP_K_PER_QUERY = 4  # por search_query do planner (máx 3 queries no schema)
FALLBACK_WHERE = {"company_name": "apple"}  # usado só se planner vier sem filters

PRINT_CHUNK_PREVIEW = 300  # chars



llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.OPENAI_API_KEY)
rag = RAGProcessor(persist_directory=PERSIST_DIR, collection_name=COLLECTION_NAME)


orchestrator = OrchestratorAgent(llm_client=llm, name="orchestrator")
extractor = ExtractorAgent(llm_client=llm, name="extractor")
sentiment = SentimentAgent(llm_client=llm, name="sentiment")
qa = QAAgent(llm_client=llm, name="qa")

AGENT_REGISTRY = {
    "extractor": extractor,
    "sentiment": sentiment,
    "qa": qa,
}

# ---------------- helpers ----------------
def now_ms() -> int:
    return int(time.time() * 1000)

def push_trace(state: AgentState, step: str, ok: bool, meta: Dict[str, Any], err: Optional[str] = None) -> AgentState:
    trace = state.get("agent_trace", [])
    trace.append({
        "ts_ms": now_ms(),
        "step": step,
        "ok": ok,
        "meta": meta,
        "error": err,
    })
    state["agent_trace"] = trace
    return state

def _dedup_docs(docs: List[dict]) -> List[dict]:
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


def node_orchestrate(state: AgentState) -> AgentState:
    try:
        plan = orchestrator.execute(state)

        state["selected_agents"] = plan.get("target_agents", [])
        state["routing_reasoning"] = plan.get("reasoning", "")

        if not state["selected_agents"]:
            state["selected_agents"] = ["qa"]

        state = push_trace(
            state,
            step="orchestrate",
            ok=True,
            meta={
                "selected_agents": state["selected_agents"],
                "n_search_queries": len(plan.get("search_queries", [])),
            },
        )
        state["agent_trace"][-1]["plan"] = plan
        return state
    except Exception:
        err = traceback.format_exc()
        state = push_trace(state, step="orchestrate", ok=False, meta={}, err=err)
        raise

def node_retrieve(state: AgentState) -> AgentState:
    try:
        # Pega o plano anterior do histórico
        last_plan = None
        for e in reversed(state.get("agent_trace", [])):
            if e.get("step") == "orchestrate" and e.get("plan"):
                last_plan = e["plan"]
                break
        
        search_queries = (last_plan.get("search_queries", []) if last_plan else [])
        
        all_docs: List[dict] = []

        if not search_queries:
            from app.schemas.schemas import RetrievalQuery
            search_queries = [RetrievalQuery(query=state["query"])]

        for sq in search_queries:
            q_text = sq.query if hasattr(sq, 'query') else sq.get('query')
            
            where_clause = {}

            f_company = sq.filter_company if hasattr(sq, 'filter_company') else sq.get('filter_company')
            f_doc = sq.filter_doc_type if hasattr(sq, 'filter_doc_type') else sq.get('filter_doc_type')

            where_clause = {
                "company_name": f_company.lower(),
                "document_type": f_doc,
            }

            if not where_clause:
                where_clause = None

            res = rag.query(query_text=q_text, n_results=DEFAULT_TOP_K_PER_QUERY, where=where_clause)
            
            if res and res.get("documents"):
                docs = [{"content": t, "metadata": m} for t, m in zip(res["documents"][0], res["metadatas"][0])]
                all_docs.extend(docs)

        all_docs = _dedup_docs(all_docs)
        state["retrieved_docs"] = all_docs

        state = push_trace(
            state,
            step="retrieve",
            ok=True,
            meta={
                "retrieved_count": len(all_docs),
                "queries_executed": len(search_queries)
            },
        )
        return state
    except Exception:
        err = traceback.format_exc()
        state = push_trace(state, step="retrieve", ok=False, meta={}, err=err)
        raise

def node_run_agents(state: AgentState) -> AgentState:
    """
    Executa os agentes selecionados pelo Orchestrator, na ordem.
    Atualiza campos do AgentState conforme retornos dos agentes.
    """
    try:
        targets = state.get("selected_agents", [])
        if not targets:
            targets = ["qa"]

        for agent_name in targets:
            agent = AGENT_REGISTRY.get(agent_name)
            if agent is None:
                state = push_trace(state, step=f"agent:{agent_name}", ok=False, meta={}, err="agent_not_registered")
                continue

            t0 = time.time()
            out = agent.execute(state)
            dt_ms = int((time.time() - t0) * 1000)

            ALLOWED = {
                "extractor": {"extracted_metrics"},
                "sentiment": {"sentiment_analysis"},
                "qa": {"answer", "confidence", "citations", "reasoning"},
            }

            for k, v in out.items():
                    if k in ALLOWED.get(agent_name, set()):
                        state[k] = v
                    else:
                        push_trace(state, step=f"agent:{agent_name}:dropped_key", ok=True, meta={"key": k})

        if state.get("answer"):
            state["final_answer"] = state["answer"]
        elif state.get("sentiment_analysis"):
            state["final_answer"] = json.dumps(state["sentiment_analysis"], ensure_ascii=False)
        elif state.get("extracted_metrics"):
            state["final_answer"] = json.dumps(state["extracted_metrics"], ensure_ascii=False)

        return state
    except Exception:
        err = traceback.format_exc()
        state = push_trace(state, step="run_agents", ok=False, meta={}, err=err)
        raise

def node_finalize(state: AgentState) -> AgentState:

    try:

        if state.get("confidence") is None:
            state["confidence"] = float(state.get("confidence") or 0.0)
        if state.get("citations") is None:
            state["citations"] = []
        state = push_trace(state, step="finalize", ok=True, meta={"has_final_answer": bool(state.get("final_answer"))})
        return state
    except Exception:
        err = traceback.format_exc()
        state = push_trace(state, step="finalize", ok=False, meta={}, err=err)
        raise

# ---------------- routing ----------------
def route_after_orchestrate(state: AgentState) -> str:
    return "retrieve"

# ---------------- build langgraph ----------------
g = StateGraph(AgentState)
g.add_node("orchestrate", node_orchestrate)
g.add_node("retrieve", node_retrieve)
g.add_node("run_agents", node_run_agents)
g.add_node("finalize", node_finalize)

g.set_entry_point("orchestrate")
g.add_conditional_edges("orchestrate", route_after_orchestrate, {"retrieve": "retrieve"})
g.add_edge("retrieve", "run_agents")
g.add_edge("run_agents", "finalize")
g.add_edge("finalize", END)

app = g.compile()


initial_state: AgentState = {
    "query": QUERY,
    "selected_agents": [],
    "routing_reasoning": "",
    "retrieved_docs": [],
    "extracted_metrics": None,
    "sentiment_analysis": None,
    "qa_reponse": None,  # NOTE: typo existe no AgentState do repo
    "agent_trace": [],
    "total_tokens": 0,
    "total_cost": 0.0,
    "final_answer": None,
    "citations": [],
    "confidence": 0.0,
}

print("=== LANGGRAPH STREAM ===")
final_state: Optional[AgentState] = None

for event in app.stream(initial_state):
    for node_name, st in event.items():
        final_state = st
        print(f"\n--- NODE: {node_name} ---")

        if node_name == "orchestrate":
            print("selected_agents:", st.get("selected_agents"))
            print("routing_reasoning:", st.get("routing_reasoning")[:500])

            # mostra o plano cru salvo no trace
            last = st.get("agent_trace", [])[-1]
            if last.get("plan"):
                print("plan:", json.dumps(last["plan"], ensure_ascii=False, indent=2, default=str))

        if node_name == "retrieve":
            docs = st.get("retrieved_docs", [])
            print("retrieved_docs:", len(docs))
            if docs:
                md0 = docs[0].get("metadata") or {}
                print("top1.meta.keys:", list(md0.keys()))
                print("top1.preview:", (docs[0].get("content") or "")[:PRINT_CHUNK_PREVIEW])

        if node_name == "run_agents":
            if st.get("extracted_metrics") is not None:
                print("extracted_metrics: OK")
            if st.get("sentiment_analysis") is not None:
                print("sentiment_analysis: OK")
            if st.get("answer"):
                print("answer.preview:", st["answer"][:800])
            if st.get("citations"):
                print("citations_count:", len(st["citations"]))
            print("confidence:", st.get("confidence"))

        if node_name == "finalize":
            print("final_answer.preview:", (st.get("final_answer") or "")[:800])
            print("trace_len:", len(st.get("agent_trace", [])))

print("\n=== FINAL (state keys) ===")
print(list(final_state.keys()) if final_state else None)

print("\n=== TRACE DUMP (últimos 6 eventos) ===")
if final_state:
    print(json.dumps(final_state.get("agent_trace", [])[-6:], ensure_ascii=False, indent=2, default=str))