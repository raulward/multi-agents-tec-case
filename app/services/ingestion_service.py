"""Servico de ingestao de fontes para o pipeline RAG.

Resolve as fontes solicitadas, executa o runner de ingestao e consolida o
resultado em um contrato de resposta para a API.
"""

import logging
import json
from pathlib import Path

from app.ai.workflows.workflow_dependencies import WorkflowDependencies
from app.core.config import settings
from app.rag.ingestion.models import SourceCatalog, SourceItem
from app.rag.ingestion.runner import run_sources
from app.schemas.api import IngestResponse, IngestionRequest

logger = logging.getLogger(__name__)


class IngestionService:
    """Coordena ingestao a partir de request direta ou catalogo local.

    A classe encapsula a resolucao de fontes, execucao do pipeline de ingestao
    e traducao do resultado para `IngestResponse`.
    """

    def __init__(self, deps: WorkflowDependencies):
        """Resumo:
            Inicializa o servico com dependencias de workflow e caminhos padrao.

        Args:
            deps (WorkflowDependencies): Dependencias compartilhadas da aplicacao.

        Returns:
            None: Nao retorna valor.
        """
        self.deps = deps
        self.catalog_path = Path("data/ingestion/source_catalog.json")
        self.processed_path = settings.DATA_DIR

    def ingest(self, req: IngestionRequest) -> IngestResponse:
        """Resumo:
            Executa a ingestao das fontes requisitadas e retorna o sumario.

        Args:
            req (IngestionRequest): Requisicao contendo fontes explicitas ou vazia para catalogo.

        Returns:
            IngestResponse: Resultado agregado com totais e falhas por fonte.
        """
        sources = self._resolve_sources(req)
        result = run_sources(sources=sources, deps=self.deps, processed_dir=self.processed_path)
        failures = result["failures"]
        return IngestResponse(
            total_requested=result["total_requested"],
            total_downloaded=result["total_downloaded"],
            total_failed=len(failures),
            failures=failures,
        )

    def _resolve_sources(self, req: IngestionRequest) -> list[SourceItem]:
        """Resumo:
            Resolve as fontes de ingestao da requisicao ou do catalogo padrao.

        Args:
            req (IngestionRequest): Requisicao recebida pela API.

        Returns:
            list[SourceItem]: Lista de fontes a serem processadas.
        """
        if req.sources:
            return req.sources
        return self._load_catalog_sources()

    def _load_catalog_sources(self) -> list[SourceItem]:
        """Resumo:
            Carrega e valida fontes a partir do arquivo de catalogo local.

        Args:
            None.

        Returns:
            list[SourceItem]: Fontes declaradas no catalogo validado.

        Raises:
            FileNotFoundError: Quando o arquivo de catalogo nao existe.
            ValueError: Quando o catalogo nao contem fontes.
        """
        resolved_catalog = self.catalog_path.resolve()
        if not resolved_catalog.exists():
            raise FileNotFoundError(f"Catalog file not found at '{resolved_catalog}'")
        payload = json.loads(resolved_catalog.read_text(encoding="utf-8"))
        catalog = SourceCatalog.model_validate(payload)
        if not catalog.sources:
            raise ValueError(f"Catalog file has no sources: '{resolved_catalog}'")
        return catalog.sources
