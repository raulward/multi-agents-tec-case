from typing import TypedDict, List, Optional, Literal


class AgentState(TypedDict):
    query: str
    selected_agents: List[str]
    routing_reasoning: str
    retrieved_docs: List[dict]
    company_catalog: List[str]
    extracted_metrics: Optional[dict]
    sentiment_analysis: Optional[dict]
    answer: Optional[str]
    agent_trace: List[dict]
    total_tokens: int
    total_cost: float
    final_answer: Optional[str]
    citations: List[dict]
    confidence: float