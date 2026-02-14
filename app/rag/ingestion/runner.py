"""Runner do pipeline de ingestao para fontes HTML/PDF.

Executa as etapas de fetch, parse, enriquecimento, chunking, indexacao e
persistencia, com rastreabilidade de eventos e tratamento de falhas por etapa.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.rag.chunker import Chunker
from app.rag.ingestion.enricher import enrich_markdown_with_llm
from app.rag.ingestion.fetcher import fetch_url
from app.rag.ingestion.models import IngestFailure, SourceItem
from app.rag.ingestion.parsers import parse_html_to_markdown, parse_pdf_to_markdown
from app.schemas.domain import Chunk, Document

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+all\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"developer\s+message", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]


@dataclass
class _StepFailure(Exception):
    """Excecao de controle para sinalizar falha em etapa especifica.

    Encapsula o nome da etapa e a excecao original para que o pipeline
    consolide falhas sem interromper o processamento das demais fontes.
    """

    step: str
    error: Exception

    def __str__(self) -> str:
        """Resumo:
            Retorna representacao textual da excecao original encapsulada.

        Args:
            None.

        Returns:
            str: Mensagem de erro da excecao encapsulada.
        """
        return str(self.error)


def run_sources(sources: list[SourceItem], deps: Any, processed_dir: str = "data/processed") -> dict[str, Any]:
    """Resumo:
        Executa a ingestao de multiplas fontes com isolamento de falhas.

    Args:
        sources (list[SourceItem]): Fontes a serem processadas no pipeline.
        deps (Any): Dependencias operacionais, incluindo acesso ao RAG.
        processed_dir (str): Diretorio para persistencia de markdown processado.

    Returns:
        dict[str, Any]: Sumario com totais de requisicoes, sucessos e falhas.
    """
    run_id = str(uuid.uuid4())
    successes = 0
    failures: list[IngestFailure] = []

    for source in sources:
        try:
            if _already_ingested(deps, source.id):
                _log_event(run_id, source, "skipped_already_ingested")
                continue
            _run_single_source(source=source, deps=deps, run_id=run_id, processed_dir=processed_dir)
            successes += 1
        except _StepFailure as exc:
            failures.append(
                IngestFailure(source_id=source.id, url=str(source.url), step=exc.step, error=str(exc.error))
            )
            _log_event(run_id, source, "failed", step_failed=exc.step, error=str(exc.error))
        except Exception as exc:
            failures.append(
                IngestFailure(source_id=source.id, url=str(source.url), step="pipeline", error=str(exc))
            )
            _log_event(run_id, source, "failed", error=str(exc))

    return {"total_requested": len(sources), "total_downloaded": successes, "failures": failures}


def _run_single_source(source: SourceItem, deps: Any, run_id: str, processed_dir: str) -> None:
    """Resumo:
        Processa uma fonte ponta a ponta no pipeline de ingestao.

    Args:
        source (SourceItem): Fonte individual a ser processada.
        deps (Any): Dependencias operacionais, incluindo servico RAG.
        run_id (str): Identificador da execucao corrente.
        processed_dir (str): Diretorio de persistencia do markdown final.

    Returns:
        None: Nao retorna valor.

    Raises:
        _StepFailure: Quando alguma etapa falha ou produz resultado invalido.
    """
    t0 = time.time()
    _log_event(run_id, source, "fetch_start")
    try:
        fetched = fetch_url(str(source.url), source.fetch)
    except Exception as exc:
        raise _StepFailure(step="fetch", error=exc) from exc
    _log_event(
        run_id,
        source,
        "fetch_done",
        elapsed_ms=_elapsed_ms(t0),
        bytes_downloaded=fetched.bytes_downloaded,
    )

    try:
        parsed = _parse_source(source=source, payload=fetched.content)
    except Exception as exc:
        raise _StepFailure(step="parse", error=exc) from exc
    if not parsed.markdown.strip():
        raise _StepFailure(step="parse", error=ValueError("empty markdown after parsing"))
    _log_event(run_id, source, "parse_to_markdown_done", elapsed_ms=_elapsed_ms(t0))

    try:
        enriched = enrich_markdown_with_llm(parsed.markdown)
    except Exception as exc:
        raise _StepFailure(step="enrich", error=exc) from exc
    _log_event(run_id, source, "enrich_llm_done", elapsed_ms=_elapsed_ms(t0))

    merged_meta = _merge_metadata(source=source, fetched=fetched, parsed_meta=parsed.base_metadata, enriched=enriched)
    try:
        chunks = Chunker().chunk(parsed.markdown, merged_meta)
    except Exception as exc:
        raise _StepFailure(step="chunk", error=exc) from exc
    if not chunks:
        raise _StepFailure(step="chunk", error=ValueError("no chunks generated from markdown"))
    _mark_suspected_injection(chunks)
    _log_event(run_id, source, "chunk_done", elapsed_ms=_elapsed_ms(t0), num_chunks=len(chunks))

    document = _build_document(source=source, markdown=parsed.markdown, metadata=merged_meta, chunks=chunks)
    try:
        deps.rag.add_document(document)
    except Exception as exc:
        raise _StepFailure(step="index", error=exc) from exc
    _log_event(run_id, source, "index_done", elapsed_ms=_elapsed_ms(t0), num_chunks=len(chunks))

    try:
        _save_markdown(source.id, parsed.markdown, processed_dir)
    except Exception as exc:
        raise _StepFailure(step="persist", error=exc) from exc
    _log_event(run_id, source, "persist_done", elapsed_ms=_elapsed_ms(t0))


def _parse_source(source: SourceItem, payload: bytes):
    """Resumo:
        Seleciona parser por tipo de fonte e converte payload para markdown.

    Args:
        source (SourceItem): Fonte com tipo e configuracoes de extracao.
        payload (bytes): Conteudo bruto obtido no download.

    Returns:
        Any: Resultado de parsing com markdown e metadados base.

    Raises:
        ValueError: Quando fonte HTML nao possui configuracao de extracao.
    """
    if source.kind == "pdf":
        return parse_pdf_to_markdown(payload, source.id)
    if source.extract is None:
        raise ValueError("extract is required for html sources")
    html_text = payload.decode("utf-8", errors="ignore")
    return parse_html_to_markdown(html_text, source.extract, source.id)


def _merge_metadata(source: SourceItem, fetched: Any, parsed_meta: dict[str, Any], enriched: Any) -> dict[str, Any]:
    """Resumo:
        Consolida metadados de origem, download, parsing e enriquecimento.

    Args:
        source (SourceItem): Fonte original da ingestao.
        fetched (Any): Resultado do fetch com URL resolvida.
        parsed_meta (dict[str, Any]): Metadados extraidos no parsing.
        enriched (Any): Metadados inferidos por enriquecimento LLM.

    Returns:
        dict[str, Any]: Metadados finais associados ao documento e chunks.
    """
    company_name = enriched.company_name.strip().lower()
    metadata: dict[str, Any] = dict(parsed_meta)
    metadata.update(
        {
            "source_id": source.id,
            "source_url": str(source.url),
            "resolved_url": fetched.resolved_url,
            "company_name": company_name,
            "document_type": enriched.document_type,
            "document_date": enriched.document_date,
        }
    )
    return metadata


def _build_document(source: SourceItem, markdown: str, metadata: dict[str, Any], chunks: list[Chunk]) -> Document:
    """Resumo:
        Cria entidade de dominio `Document` a partir do conteudo processado.

    Args:
        source (SourceItem): Fonte de origem do documento.
        markdown (str): Conteudo textual consolidado em markdown.
        metadata (dict[str, Any]): Metadados finais do documento.
        chunks (list[Chunk]): Chunks gerados para indexacao.

    Returns:
        Document: Documento pronto para indexacao no RAG.
    """
    return Document(
        id=source.id,
        company_name=metadata.get("company_name", "unknown"),
        num_chunks=len(chunks),
        text=markdown,
        chunks=chunks,
        metadata=metadata,
    )


def _mark_suspected_injection(chunks: list[Chunk]) -> None:
    """Resumo:
        Marca chunks com suspeita de prompt injection com base em padroes regex.

    Args:
        chunks (list[Chunk]): Lista de chunks a serem avaliados.

    Returns:
        None: Nao retorna valor.
    """
    for chunk in chunks:
        text = chunk.text or ""
        suspected = any(pattern.search(text) for pattern in INJECTION_PATTERNS)
        chunk.metadata["suspected_injection"] = suspected


def _save_markdown(source_id: str, markdown: str, processed_dir: str) -> None:
    """Resumo:
        Persiste o markdown processado em arquivo no diretorio configurado.

    Args:
        source_id (str): Identificador da fonte processada.
        markdown (str): Conteudo em markdown a ser salvo.
        processed_dir (str): Diretorio de destino para arquivo final.

    Returns:
        None: Nao retorna valor.
    """
    folder = Path(processed_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{source_id}.md").write_text(markdown, encoding="utf-8")


def _already_ingested(deps: Any, source_id: str) -> bool:
    """Resumo:
        Verifica se a fonte ja possui chunks indexados no RAG.

    Args:
        deps (Any): Dependencias contendo acesso ao backend vetorial.
        source_id (str): Identificador da fonte consultada.

    Returns:
        bool: `True` quando ao menos um chunk existente e encontrado.
    """
    data = deps.rag.rag.collection.get(where={"source_id": source_id}, limit=1)
    ids = data.get("ids") or []
    return len(ids) > 0


def _elapsed_ms(t0: float) -> int:
    """Resumo:
        Calcula tempo decorrido desde `t0` em milissegundos.

    Args:
        t0 (float): Timestamp inicial em segundos.

    Returns:
        int: Tempo decorrido em milissegundos.
    """
    return int((time.time() - t0) * 1000)


def _log_event(run_id: str, source: SourceItem, step: str, **extra: Any) -> None:
    """Resumo:
        Registra evento estruturado de ingestao no logger da aplicacao.

    Args:
        run_id (str): Identificador da execucao corrente.
        source (SourceItem): Fonte relacionada ao evento.
        step (str): Nome da etapa registrada.
        **extra (Any): Campos adicionais anexados ao evento.

    Returns:
        None: Nao retorna valor.
    """
    event = {"run_id": run_id, "source_id": source.id, "kind": source.kind, "url": str(source.url), "step": step}
    event.update(extra)
    logger.info("ingestion_event=%s", json.dumps(event, ensure_ascii=False))
