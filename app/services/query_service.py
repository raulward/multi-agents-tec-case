"""Servico de execucao de consultas no workflow multiagente.

Inicia uma execucao com `run_id`, consome os eventos emitidos pelo grafo e
converte o estado final para o contrato de resposta da API.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.ai.workflows.workflow import create_initial_state
from app.schemas.api import QueryResponse

logger = logging.getLogger(__name__)


class QueryService:
    """Orquestra a chamada do workflow e serializa o resultado para resposta externa.

    A classe administra o ciclo de vida de uma consulta unica e transforma
    estruturas internas do estado em `QueryResponse`.
    """

    def __init__(self, workflow_app, deps):
        """Resumo:
            Inicializa o servico com a aplicacao de workflow e dependencias.

        Args:
            workflow_app (Any): Aplicacao/grafo com suporte a stream de eventos.
            deps (Any): Dependencias compartilhadas do workflow.

        Returns:
            None: Nao retorna valor.
        """
        self.workflow_app = workflow_app
        self.deps = deps

    def run(self, query: str) -> QueryResponse:
        """Resumo:
            Executa o workflow para uma pergunta e retorna a resposta da API.

        Args:
            query (str): Pergunta enviada pelo usuario.

        Returns:
            QueryResponse: Resposta final com answer, citacoes, roteamento e trace.

        Raises:
            RuntimeError: Quando o workflow nao produz estado final.
        """
        run_id = str(uuid.uuid4())
        logger.info("Starting query run_id=%s", run_id)
        initial_state = create_initial_state(
            query,
            company_catalog=self.deps.company_catalog,
            doc_types=self.deps.doc_types,
            run_id=run_id,
        )

        final_state: Optional[Dict[str, Any]] = None
        for event in self.workflow_app.stream(initial_state):
            for _, st in event.items():
                final_state = st

        if final_state is None:
            raise RuntimeError("Workflow produced no output")

        raw_citations = final_state.get("citations") or []
        citations = self._parse_citations(raw_citations)

        resp = self._build_query_response(final_state, citations)

        return resp

    def _parse_citations(self, raw_citations: List) -> List[Dict[str, Any]]:
        """Resumo:
            Normaliza citacoes para dicionarios serializaveis.

        Args:
            raw_citations (List): Lista de citacoes em dicts ou modelos com `model_dump`.

        Returns:
            List[Dict[str, Any]]: Lista de citacoes convertidas para dicionario.
        """
        return [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in raw_citations
        ]

    def _build_query_response(self, final_state: Dict[str, Any], citations: List[Dict[str, Any]]):
        """Resumo:
            Monta o objeto de resposta publica a partir do estado final.

        Args:
            final_state (Dict[str, Any]): Estado final produzido pelo workflow.
            citations (List[Dict[str, Any]]): Citacoes ja normalizadas.

        Returns:
            QueryResponse: Objeto tipado de resposta para a camada de API.
        """
        return QueryResponse(
            final_answer=final_state.get("final_answer"),
            confidence=float(final_state.get("confidence", 0.0) or 0.0),
            citations=citations,
            extracted_metrics=final_state.get("extracted_metrics"),
            sentiment_analysis=final_state.get("sentiment_analysis"),
            routing={
                "selected_agents": final_state.get("selected_agents", []),
                "reasoning": final_state.get("routing_reasoning", ""),
            },
            trace=final_state.get("agent_trace", []),
        )
