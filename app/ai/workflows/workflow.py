from langgraph.graph import StateGraph, END

from app.ai.workflows.state import AgentState
from app.ai.workflows.nodes import WorkflowNodes
from app.ai.workflows.workflow_dependencies import WorkflowDependencies

def build_workflows(deps: WorkflowDependencies) -> StateGraph:

    nodes = WorkflowNodes(
        orchestrator=deps.orchestrator,
        rag_processor=deps.rag,
        agent_registry=deps.agent_registry
    )

    graph = StateGraph(AgentState)

    graph.add_node("orchestrate", nodes.orchestrate)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("run_agents", nodes.run_agents)
    graph.add_node("finalize", nodes.finalize)

    graph.set_entry_point("orchestrate")

    graph.add_conditional_edges(
        "orchestrate",
        nodes.route_after_orchestrate,  
        {
            "retrieve": "retrieve",
            "run_agents": "run_agents",
            "finalize": "finalize",
        },
    )
    graph.add_edge("retrieve", "run_agents")
    graph.add_edge("run_agents", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def create_initial_state(query: str, company_catalog: list[str]) -> AgentState:

    return {
        "query": query,
        "company_catalog": company_catalog,
        "selected_agents": [],
        "routing_reasoning": "",
        "search_queries": [],
        "retrieved_docs": [],
        "extracted_metrics": None,
        "sentiment_analysis": None,
        "answer": None,
        "agent_trace": [],
        "total_tokens": 0,
        "total_cost": 0.0,
        "final_answer": None,
        "citations": [],
        "confidence": 0.0,
    }