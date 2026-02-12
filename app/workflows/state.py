from typing import TypedDict, List, Optional, Literal
from pydantic import BaseModel

class AgentState(TypedDict):
    query: str
    
    selected_agents: List[str]
    routing_reasoning: str

    retrieved_docs: List[dict]

    extracted_metrics: Optional[dict]
    sentiment_analysis: Optional[dict]
    qa_reponse: Optional[str]

    agent_trace: List[dict]
    total_tokens: int
    total_cost: float

    final_answer: Optional[str]
    citations: List[dict]
    confidence: float