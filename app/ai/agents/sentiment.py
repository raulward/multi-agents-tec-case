"""Agente especialista em analise de sentimento e risco.

Processa o contexto recuperado para estimar polaridade, riscos-chave e destaques
positivos com saida estruturada para consumo no workflow.
"""

from app.ai.agents.base import BaseAgent
from typing import Dict, Any

from app.ai.prompts.sentiment.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.sentiment.human_prompt import HUMAN_PROMPT

from app.ai.workflows.state import AgentState

from app.ai.structured_output.sentiment import RiskAssessment
from langchain_core.prompts import ChatPromptTemplate

class SentimentAgent(BaseAgent):
    """Gera avaliacao de sentimento com contrato de saida fixo.

    O agente produz apenas `sentiment_analysis` usando prompts dedicados e
    validacao estruturada.
    """

    produces = {"sentiment_analysis"}

    def __init__(self, llm_client, name="sentiment"):
        """Resumo:
            Inicializa o agente de sentimento e seu cliente estruturado.

        Args:
            llm_client (Any): Cliente LLM base usado para inferencia.
            name (str): Nome identificador do agente.

        Returns:
            None: Nao retorna valor.
        """
        super().__init__(llm_client, name)
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(RiskAssessment)

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Resumo:
            Analisa sentimento/riscos a partir dos documentos recuperados.

            Chaves de `state` lidas: `query`, `retrieved_docs`.
            Chaves de `state` escritas: Nenhuma (retorna payload de saida).

        Args:
            state (AgentState): Estado atual do workflow.

        Returns:
            Dict[str, Any]: Dicionario com a chave `sentiment_analysis`.
        """
        query = state["query"]
        docs = state.get("retrieved_docs", [])

        if not docs:
            empty = RiskAssessment(
                sentiment="neutral",
                key_risks=[],
                positive_highlights=[],
                overall_rationale="No documents provided.",
                confidence=0.0,
            )
            return {
                "sentiment_analysis": empty.model_dump(),
            }

        context = self._build_context(docs)

        human_prompt = HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | self.client_structured


        result: RiskAssessment = chain.invoke({
            "query": query,
            "context": context,
        })

        return {
            "sentiment_analysis": result.model_dump(),
        }
