"""Agente especialista em extracao de metricas estruturadas.

Converte contexto recuperado em um sumario de indicadores financeiros e
operacionais, retornando um payload estruturado para o workflow.
"""

from app.ai.agents.base import BaseAgent
from typing import Dict, Any, List
import json

from app.ai.prompts.extractor.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.extractor.human_prompt import HUMAN_PROMPT

from app.ai.workflows.state import AgentState

from app.ai.structured_output.extractor import ExtractionResult
from langchain_core.prompts import ChatPromptTemplate

class ExtractorAgent(BaseAgent):
    """Executa extracao de metricas com saida tipada.

    Este agente usa prompt especifico de extracao e devolve apenas a chave
    `extracted_metrics` conforme o contrato de producao.
    """

    produces = {"extracted_metrics"}

    def __init__(self, llm_client, name="extractor"):
        """Resumo:
            Inicializa o agente de extracao e seu cliente estruturado.

        Args:
            llm_client (Any): Cliente LLM base usado para inferencia.
            name (str): Nome identificador do agente.

        Returns:
            None: Nao retorna valor.
        """
        super().__init__(llm_client, name)
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(ExtractionResult)

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Resumo:
            Extrai metricas do contexto recuperado e retorna payload estruturado.

            Chaves de `state` lidas: `query`, `retrieved_docs`.
            Chaves de `state` escritas: Nenhuma (retorna payload de saida).

        Args:
            state (AgentState): Estado atual do workflow.

        Returns:
            Dict[str, Any]: Dicionario com a chave `extracted_metrics`.
        """
        query = state["query"]
        docs = state.get("retrieved_docs", [])

        if not docs:
            return {
                "extracted_metrics": ExtractionResult(
                    company="Unknown",
                    metrics=[],
                    summary="No documents provided for extraction.",
                    confidence=0.0
                ).model_dump(),
            }
    
        context = self._build_context(docs)

        human_prompt = HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | self.client_structured

        extracts: ExtractionResult = chain.invoke({
            "query": query,
            "context": context
        })

        return {
            "extracted_metrics": extracts.model_dump(),
        }
