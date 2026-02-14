from typing import List, Optional, TypedDict


class AgentState(TypedDict):
    run_id: str
    query: str
    selected_agents: List[str]
    routing_reasoning: str
    search_queries: List[dict]
    retrieved_docs: List[dict]
    company_catalog: List[str]
    doc_types: List[str]
    extracted_metrics: Optional[dict]
    sentiment_analysis: Optional[dict]
    answer: Optional[str]
    agent_trace: List[dict]
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    final_answer: Optional[str]
    citations: List[dict]
    confidence: float
