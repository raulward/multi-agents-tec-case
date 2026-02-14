"""Agente de roteamento de alto nivel para o workflow.

Analisa a pergunta, seleciona quais agentes especialistas devem rodar e define
consultas de busca estruturadas para recuperacao de contexto.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.ai.prompts.orchestrator.human_prompt import HUMAN_PROMPT
from app.ai.prompts.orchestrator.system_prompt import SYSTEM_PROMPT
from app.ai.structured_output.orchestrator import OrchestratorPlan
from app.ai.workflows.state import AgentState

from .base import BaseAgent


class OrchestratorAgent(BaseAgent):
    """Define plano de execucao dos agentes e consultas de recuperacao.

    Este agente usa saida estruturada para produzir agentes alvo, consultas de
    busca e justificativa de roteamento.
    """

    def __init__(self, llm_client, name, company_catalog=None, doc_types=None):
        """Resumo:
            Inicializa o agente orquestrador e seu cliente estruturado.

        Args:
            llm_client (Any): Cliente LLM base usado para inferencia.
            name (Any): Nome recebido na chamada de construcao.
            company_catalog (Any): Catalogo padrao de empresas disponiveis.
            doc_types (Any): Tipos documentais padrao permitidos.

        Returns:
            None: Nao retorna valor.
        """
        super().__init__(llm_client, name="orchestrator")
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(OrchestratorPlan)
        self.company_catalog = company_catalog or []
        self.doc_types = doc_types or []

    def execute(self, state: AgentState):
        """Resumo:
            Gera plano de roteamento e consultas de busca a partir do estado.

            Chaves de `state` lidas: `query`, `company_catalog`, `doc_types`.
            Chaves de `state` escritas: Nenhuma (retorna payload de saida).

        Args:
            state (AgentState): Estado atual do workflow.

        Returns:
            Dict[str, Any]: Dicionario com `search_queries`, `target_agents` e `reasoning`.
        """
        query = state["query"]

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", HUMAN_PROMPT),
        ])

        companies_available = state.get("company_catalog") or self.company_catalog
        doc_types_available = state.get("doc_types") or self.doc_types
        plan = (prompt | self.client_structured).invoke(
            {
                "query": query,
                "companies_available": companies_available,
                "doc_types_available": doc_types_available,
            }
        )

        search_queries = [q.model_dump() for q in plan.search_queries]
        target_agents = [a for a in plan.target_agents if a in {"extractor", "sentiment"}]

        return {
            "search_queries": search_queries,
            "target_agents": target_agents,
            "reasoning": plan.reasoning,
        }
