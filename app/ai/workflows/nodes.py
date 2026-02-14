"""Nos de execucao do workflow multiagente.

Coordena roteamento, recuperacao de contexto no RAG, execucao de agentes e
consolidacao da resposta final com trilha de auditoria e custos.
"""

import json
import logging
import time
import traceback
from typing import Any, Dict, List

from langchain_community.callbacks.manager import get_openai_callback

from app.ai.agents.orchestrator import OrchestratorAgent
from app.ai.workflows.state import AgentState
from app.core.config import settings
from app.core.costs import CostCalculator
from app.rag.rag_service import RagService

logger = logging.getLogger(__name__)


class WorkflowNodes:
    """Orquestra as etapas principais do workflow orientado por estado.

    A classe aplica o plano de roteamento, busca documentos, executa agentes
    registrados e acumula metadados operacionais no proprio `state`.
    """

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        rag_processor: RagService,
        agent_registry: Dict[str, Any],
    ):
        """Resumo:
            Inicializa o orquestrador de nos com dependencias de agentes e RAG.

        Args:
            orchestrator (OrchestratorAgent): Agente responsavel pelo roteamento.
            rag_processor (RagService): Servico de recuperacao de documentos.
            agent_registry (Dict[str, Any]): Registro de agentes por nome.

        Returns:
            None: Nao retorna valor.
        """
        self.orchestrator = orchestrator
        self.rag = rag_processor
        self.agent_registry = agent_registry

    def orchestrate(self, state: AgentState) -> AgentState:
        """Resumo:
            Executa o agente orquestrador e atualiza o roteamento no estado.

            Chaves de `state` lidas: `query`, `company_catalog`, `doc_types`,
            `search_queries`.
            Chaves de `state` escritas: `selected_agents`, `routing_reasoning`,
            `search_queries`, `agent_trace`.

        Args:
            state (AgentState): Estado compartilhado do workflow.

        Returns:
            AgentState: Estado atualizado com plano de roteamento.

        Raises:
            Exception: Repropaga qualquer erro ocorrido durante o roteamento.
        """
        t0 = time.time()
        try:
            plan = self.orchestrator.execute(state)
            selected = []
            for agent_name in plan.get("target_agents", []) or []:
                if agent_name in {"extractor", "sentiment"} and agent_name not in selected:
                    selected.append(agent_name)

            state["selected_agents"] = selected
            state["routing_reasoning"] = plan.get("reasoning", "")
            state["search_queries"] = plan.get("search_queries", []) or []

            self._push_trace(
                state,
                step="orchestrate",
                meta={
                    "dt_ms": int((time.time() - t0) * 1000),
                    "selected_filters": [
                        {
                            "query": q.get("query"),
                            "filter_company": q.get("filter_company"),
                            "filter_doc_type": q.get("filter_doc_type"),
                        }
                        for q in state.get("search_queries", [])
                    ],
                },
            )
            return state
        except Exception:
            self._push_trace(
                state,
                step="orchestrate",
                meta={"dt_ms": int((time.time() - t0) * 1000)},
                err=traceback.format_exc(),
            )
            raise

    def retrieve(self, state: AgentState) -> AgentState:
        """Resumo:
            Recupera documentos no RAG com base nas consultas planejadas.

            Chaves de `state` lidas: `search_queries`, `query`.
            Chaves de `state` escritas: `retrieved_docs`, `agent_trace`.

        Args:
            state (AgentState): Estado compartilhado do workflow.

        Returns:
            AgentState: Estado atualizado com documentos recuperados e trace.

        Raises:
            Exception: Repropaga qualquer erro ocorrido durante a recuperacao.
        """
        t0 = time.time()
        try:
            docs, retrieval_meta = self.rag.retrieve(
                search_queries=state.get("search_queries") or [],
                user_query=state.get("query") or "",
            )
            state["retrieved_docs"] = docs

            self._push_trace(
                state,
                step="retrieve",
                meta={
                    "dt_ms": int((time.time() - t0) * 1000),
                    "retrieved_count": retrieval_meta.get("retrieved_count", len(docs)),
                    "retrieved_id": self._extract_retrieved_ids(docs),
                    "fallback_used": bool(retrieval_meta.get("fallback_used", False)),
                    "queries_executed": retrieval_meta.get("queries_executed", 0),
                },
            )
            return state
        except Exception:
            self._push_trace(
                state,
                step="retrieve",
                meta={"dt_ms": int((time.time() - t0) * 1000)},
                err=traceback.format_exc(),
            )
            raise

    def run_agents(self, state: AgentState) -> AgentState:
        """Resumo:
            Define a ordem de execucao e roda os agentes selecionados.

            Chaves de `state` lidas: `selected_agents`.
            Chaves de `state` escritas: `agent_trace` e chaves produzidas por
            cada agente registrado.

        Args:
            state (AgentState): Estado compartilhado do workflow.

        Returns:
            AgentState: Estado atualizado apos a execucao dos agentes.
        """
        t0 = time.time()
        selected = state.get("selected_agents", []) or []
        execution_order: List[str] = []

        if "extractor" in selected:
            execution_order.append("extractor")
        if "sentiment" in selected:
            execution_order.append("sentiment")
        execution_order.append("qa")

        self._push_trace(
            state,
            step="run_agents",
            meta={
                "dt_ms": int((time.time() - t0) * 1000),
                "execution_order": execution_order,
            },
        )

        for agent_name in execution_order:
            self._run_single_agent(state, agent_name)

        return state

    def finalize(self, state: AgentState) -> AgentState:
        """Resumo:
            Garante campos finais obrigatorios e monta a resposta final.

            Chaves de `state` lidas: `confidence`, `citations`, `answer`,
            `extracted_metrics`, `sentiment_analysis`, `total_tokens`,
            `total_cost`.
            Chaves de `state` escritas: `confidence`, `citations`,
            `final_answer`, `agent_trace`.

        Args:
            state (AgentState): Estado compartilhado do workflow.

        Returns:
            AgentState: Estado finalizado para resposta da API.

        Raises:
            Exception: Repropaga qualquer erro ocorrido na finalizacao.
        """
        t0 = time.time()
        try:
            if state.get("confidence") is None:
                state["confidence"] = 0.0
            if state.get("citations") is None:
                state["citations"] = []

            state["final_answer"] = self._compose_final_answer(state)

            self._push_trace(
                state,
                step="finalize",
                meta={
                    "dt_ms": int((time.time() - t0) * 1000),
                    "total_tokens": state.get("total_tokens"),
                    "total_cost_usd": state.get("total_cost"),
                },
            )
            return state
        except Exception:
            self._push_trace(
                state,
                step="finalize",
                meta={"dt_ms": int((time.time() - t0) * 1000)},
                err=traceback.format_exc(),
            )
            raise

    def _run_single_agent(self, state: AgentState, agent_name: str) -> None:
        """Resumo:
            Executa um agente individual, restringe chaves permitidas e acumula custos.

            Chaves de `state` lidas: `run_id`, `total_input_tokens`,
            `total_output_tokens`, `total_cost` e chaves usadas pelo agente.
            Chaves de `state` escritas: saidas permitidas por `produces`,
            `total_input_tokens`, `total_output_tokens`, `total_tokens`,
            `total_cost`, `agent_trace`.

        Args:
            state (AgentState): Estado compartilhado do workflow.
            agent_name (str): Nome do agente a ser executado.

        Returns:
            None: Nao retorna valor.

        Raises:
            TypeError: Quando a saida do agente nao e um dicionario.
        """
        agent = self.agent_registry.get(agent_name)
        if agent is None:
            self._push_trace(
                state,
                step=f"agent:{agent_name}",
                meta={"dt_ms": 0},
                err="agent_not_registered",
            )
            return

        allowed_keys = getattr(agent, "produces", None)
        if not allowed_keys:
            self._push_trace(
                state,
                step=f"agent:{agent_name}",
                meta={"dt_ms": 0},
                err="agent_missing_produces",
            )
            return

        t0 = time.time()
        out = None
        callback = None
        input_tokens = None
        output_tokens = None
        returned_keys: List[str] = []
        applied_keys: List[str] = []
        dropped_keys: List[str] = []
        model_name = getattr(
            getattr(agent, "client_structured", None),
            "model_name",
            getattr(getattr(agent, "client", None), "model_name", settings.MODEL_NAME),
        )

        try:
            with get_openai_callback() as callback:
                out = agent.execute(state)

            if callback is not None:
                input_tokens = getattr(callback, "prompt_tokens", None)
                output_tokens = getattr(callback, "completion_tokens", None)

            cost = CostCalculator.calculate(model_name, input_tokens, output_tokens)
            self._accumulate_costs(state, cost.input_tokens, cost.output_tokens, cost.cost_usd)

            if not isinstance(out, dict):
                raise TypeError(f"agent_output_not_dict: {type(out).__name__}")

            returned_keys = list(out.keys())
            for key, value in out.items():
                if key in allowed_keys:
                    state[key] = value
                    applied_keys.append(key)
                else:
                    dropped_keys.append(key)

            payload_meta: Dict[str, Any] = {}
            if agent_name == "extractor":
                if "extracted_metrics" in out:
                    payload_meta["extracted_metrics"] = out.get("extracted_metrics")
                elif state.get("extracted_metrics") is not None:
                    payload_meta["extracted_metrics"] = state.get("extracted_metrics")
            elif agent_name == "sentiment":
                if "sentiment_analysis" in out:
                    payload_meta["sentiment_analysis"] = out.get("sentiment_analysis")
                elif state.get("sentiment_analysis") is not None:
                    payload_meta["sentiment_analysis"] = state.get("sentiment_analysis")
            elif agent_name == "qa":
                for field in ("answer", "reasoning", "citations", "confidence"):
                    if field in out:
                        payload_meta[field] = out.get(field)
                    elif state.get(field) is not None:
                        payload_meta[field] = state.get(field)

            self._push_trace(
                state,
                step=f"agent:{agent_name}",
                meta={
                    "dt_ms": int((time.time() - t0) * 1000),
                    "model_name": model_name,
                    "input_tokens": cost.input_tokens,
                    "output_tokens": cost.output_tokens,
                    "cost_usd": cost.cost_usd,
                    "returned_keys": returned_keys,
                    "applied_keys": applied_keys,
                    "dropped_keys": dropped_keys,
                    **payload_meta,
                },
            )
        except Exception:
            if callback is not None:
                input_tokens = getattr(callback, "prompt_tokens", None)
                output_tokens = getattr(callback, "completion_tokens", None)
            cost = CostCalculator.calculate(model_name, input_tokens, output_tokens)
            self._accumulate_costs(state, cost.input_tokens, cost.output_tokens, cost.cost_usd)

            if isinstance(out, dict):
                returned_keys = list(out.keys())

            payload_meta: Dict[str, Any] = {}
            if agent_name == "extractor" and state.get("extracted_metrics") is not None:
                payload_meta["extracted_metrics"] = state.get("extracted_metrics")
            elif agent_name == "sentiment" and state.get("sentiment_analysis") is not None:
                payload_meta["sentiment_analysis"] = state.get("sentiment_analysis")
            elif agent_name == "qa":
                for field in ("answer", "reasoning", "citations", "confidence"):
                    if state.get(field) is not None:
                        payload_meta[field] = state.get(field)

            self._push_trace(
                state,
                step=f"agent:{agent_name}",
                meta={
                    "dt_ms": int((time.time() - t0) * 1000),
                    "model_name": model_name,
                    "input_tokens": cost.input_tokens,
                    "output_tokens": cost.output_tokens,
                    "cost_usd": cost.cost_usd,
                    "returned_keys": returned_keys,
                    "applied_keys": applied_keys,
                    "dropped_keys": dropped_keys,
                    **payload_meta,
                },
                err=traceback.format_exc(),
            )
            logger.exception("Agent execution failed run_id=%s agent=%s", state.get("run_id"), agent_name)

    def _compose_final_answer(self, state: AgentState) -> str:
        """Resumo:
            Monta a resposta final priorizando resposta direta e sinais estruturados.

            Chaves de `state` lidas: `answer`, `extracted_metrics`,
            `sentiment_analysis`.
            Chaves de `state` escritas: Nenhuma.

        Args:
            state (AgentState): Estado compartilhado do workflow.

        Returns:
            str: Texto final retornado ao usuario.
        """
        if state.get("answer"):
            return state["answer"]
        if state.get("extracted_metrics"):
            return json.dumps(state["extracted_metrics"], ensure_ascii=False)
        if state.get("sentiment_analysis"):
            return json.dumps(state["sentiment_analysis"], ensure_ascii=False)
        return "Nao encontrei evidencias suficientes nos documentos para responder com seguranca."

    def _extract_retrieved_ids(self, docs: List[dict]) -> List[str]:
        """Resumo:
            Extrai identificadores de chunks a partir dos documentos recuperados.

        Args:
            docs (List[dict]): Lista de documentos com campos de conteudo e metadados.

        Returns:
            List[str]: Lista de identificadores de chunks encontrados.
        """
        ids: List[str] = []
        for doc in docs:
            metadata = doc.get("metadata") or {}
            chunk_id = metadata.get("chunk_id") or doc.get("chunk_id")
            if chunk_id:
                ids.append(str(chunk_id))
        return ids

    def _accumulate_costs(self, state: AgentState, input_tokens: Any, output_tokens: Any, cost_usd: Any) -> None:
        """Resumo:
            Soma tokens e custo acumulado no estado da execucao.

            Chaves de `state` lidas: `total_input_tokens`, `total_output_tokens`,
            `total_cost`.
            Chaves de `state` escritas: `total_input_tokens`,
            `total_output_tokens`, `total_tokens`, `total_cost`.

        Args:
            state (AgentState): Estado compartilhado do workflow.
            input_tokens (Any): Total de tokens de entrada da etapa.
            output_tokens (Any): Total de tokens de saida da etapa.
            cost_usd (Any): Custo monetario da etapa em USD.

        Returns:
            None: Nao retorna valor.
        """
        if isinstance(input_tokens, int):
            state["total_input_tokens"] = state.get("total_input_tokens", 0) + input_tokens
        if isinstance(output_tokens, int):
            state["total_output_tokens"] = state.get("total_output_tokens", 0) + output_tokens

        state["total_tokens"] = state.get("total_input_tokens", 0) + state.get("total_output_tokens", 0)

        if isinstance(cost_usd, (int, float)):
            state["total_cost"] = round(float(state.get("total_cost", 0.0)) + float(cost_usd), 8)

    def _push_trace(self, state: AgentState, step: str, meta: Dict[str, Any], err: str | None = None) -> None:
        """Resumo:
            Registra um evento de rastreabilidade da pipeline no estado.

            Chaves de `state` lidas: `agent_trace`.
            Chaves de `state` escritas: `agent_trace`.

        Args:
            state (AgentState): Estado compartilhado do workflow.
            step (str): Nome da etapa registrada.
            meta (Dict[str, Any]): Metadados adicionais do evento.
            err (str | None): Erro serializado, quando existente.

        Returns:
            None: Nao retorna valor.
        """
        trace = state.get("agent_trace", [])
        trace.append(
            {
                "step": step,
                "dt_ms": int((meta or {}).get("dt_ms", 0) or 0),
                "meta": meta,
                "error": err,
            }
        )
        state["agent_trace"] = trace
