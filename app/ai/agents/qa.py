"""Agente final de resposta e citacoes.

Consolida contexto recuperado e sinais estruturados de outros agentes para
produzir resposta final, confianca e citacoes.
"""

import json
from typing import Any, Dict

from app.ai.agents.base import BaseAgent
from app.ai.structured_output.qa import QAAnswer

from app.ai.prompts.qa.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.qa.human_prompt import HUMAN_PROMPT

from app.ai.workflows.state import AgentState
from langchain_core.prompts import ChatPromptTemplate

class QAAgent(BaseAgent):
    """Responsavel por sintetizar a resposta final do workflow.

    O agente combina evidencias textuais e saidas estruturadas para gerar
    `answer`, `reasoning`, `citations` e `confidence`.
    """

    produces = {"answer", "confidence", "citations", "reasoning"}

    def __init__(self, llm_client, name="qa"):
        """Resumo:
            Inicializa o agente de QA e seu cliente estruturado.

        Args:
            llm_client (Any): Cliente LLM base usado para inferencia.
            name (str): Nome identificador do agente.

        Returns:
            None: Nao retorna valor.
        """
        super().__init__(llm_client, name)
        self.system_prompt = SYSTEM_PROMPT
        self.client_structured = self.client.with_structured_output(QAAnswer)

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Resumo:
            Gera a resposta final com citacoes e nivel de confianca.

            Chaves de `state` lidas: `query`, `retrieved_docs`,
            `extracted_metrics`, `sentiment_analysis`.
            Chaves de `state` escritas: Nenhuma (retorna payload de saida).

        Args:
            state (AgentState): Estado atual do workflow.

        Returns:
            Dict[str, Any]: Dicionario com `answer`, `reasoning`, `citations`
            e `confidence`.
        """
        query = state["query"]
        docs = state.get("retrieved_docs", [])
        extracted_metrics = state.get("extracted_metrics")
        sentiment_analysis = state.get("sentiment_analysis")

        if not docs and not extracted_metrics and not sentiment_analysis:
            return {
                "answer": "Nao encontrei evidencias suficientes nos documentos para responder com seguranca.",
                "reasoning": "Nao havia contexto recuperado nem sinais estruturados suficientes para responder com seguranca.",
                "citations": [],
                "confidence": 0.0,
            }

        context = self._build_context(docs)

        human_prompt = HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", human_prompt)
        ])

        chain = prompt | self.client_structured

        response: QAAnswer = chain.invoke(
            {
                "query": query,
                "context": context,
                "extracted_metrics": json.dumps(extracted_metrics, ensure_ascii=False) if extracted_metrics else "{}",
                "sentiment_analysis": json.dumps(sentiment_analysis, ensure_ascii=False) if sentiment_analysis else "{}",
            }
        )

        return {
            "answer": response.answer,
            "reasoning": response.reasoning,
            "citations": response.citations,
            "confidence": response.confidence
        }

