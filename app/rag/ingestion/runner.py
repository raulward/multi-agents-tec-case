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
from app.rag.ingestion.dispatcher import IngestionDispatcher
from app.rag.ingestion.enricher import MarkdownEnricher
from app.rag.ingestion.fetcher import UrlFetcher
from app.rag.ingestion.html_ingestor import HtmlIngestor
from app.rag.ingestion.models import IngestFailure, SourceItem
from app.rag.ingestion.parsers import HtmlMarkdownParser, PdfMarkdownParser
from app.rag.ingestion.pdf_ingestor import PdfIngestor
from app.rag.ingestion.types import FetcherProtocol, PipelineIngestorProtocol, SourceType
from app.rag.pdf_processor import PDFProcessor
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
    """Excecao de controle para sinalizar falha em etapa especifica."""

    step: str
    error: Exception

    def __str__(self) -> str:
        return str(self.error)


class IngestionRunner:
    """Orquestrador do pipeline de ingestao."""

    def __init__(
        self,
        fetcher: FetcherProtocol | None = None,
        dispatcher: IngestionDispatcher | None = None,
        chunker: Chunker | None = None,
        processed_dir: str = "data/processed",
    ) -> None:
        self._fetcher = fetcher or UrlFetcher()
        self._chunker = chunker or Chunker()
        self._processed_dir = processed_dir
        self._dispatcher = dispatcher or self._build_default_dispatcher(fetcher=self._fetcher)

    def run_sources(self, sources: list[SourceItem], deps: Any, processed_dir: str | None = None) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        successes = 0
        failures: list[IngestFailure] = []
        target_dir = processed_dir or self._processed_dir

        for source in sources:
            try:
                if self._already_ingested(deps, source.id):
                    self._log_event(run_id, source, "skipped_already_ingested")
                    continue
                self._run_single_source(source=source, deps=deps, run_id=run_id, processed_dir=target_dir)
                successes += 1
            except _StepFailure as exc:
                failures.append(
                    IngestFailure(source_id=source.id, url=str(source.url), step=exc.step, error=str(exc.error))
                )
                self._log_event(run_id, source, "failed", step_failed=exc.step, error=str(exc.error))
            except Exception as exc:
                failures.append(IngestFailure(source_id=source.id, url=str(source.url), step="pipeline", error=str(exc)))
                self._log_event(run_id, source, "failed", error=str(exc))

        return {"total_requested": len(sources), "total_downloaded": successes, "failures": failures}

    def _run_single_source(self, source: SourceItem, deps: Any, run_id: str, processed_dir: str) -> None:
        t0 = time.time()
        self._log_event(run_id, source, "fetch_start")
        try:
            fetched = self._fetcher.fetch(str(source.url), source.fetch)
        except Exception as exc:
            raise _StepFailure(step="fetch", error=exc) from exc
        self._log_event(
            run_id,
            source,
            "fetch_done",
            elapsed_ms=self._elapsed_ms(t0),
            bytes_downloaded=fetched.bytes_downloaded,
        )

        ingestor = self._get_pipeline_ingestor(source.kind)

        try:
            parsed = ingestor.parse(source=source, payload=fetched.content)
        except Exception as exc:
            raise _StepFailure(step="parse", error=exc) from exc
        if not parsed.markdown.strip():
            raise _StepFailure(step="parse", error=ValueError("empty markdown after parsing"))
        self._log_event(run_id, source, "parse_to_markdown_done", elapsed_ms=self._elapsed_ms(t0))

        try:
            enriched = ingestor.enrich(parsed.markdown)
        except Exception as exc:
            raise _StepFailure(step="enrich", error=exc) from exc
        self._log_event(run_id, source, "enrich_llm_done", elapsed_ms=self._elapsed_ms(t0))

        merged_meta = self._merge_metadata(
            source=source,
            fetched=fetched,
            parsed_meta=parsed.base_metadata,
            enriched=enriched,
        )
        try:
            chunks = self._chunker.chunk(parsed.markdown, merged_meta)
        except Exception as exc:
            raise _StepFailure(step="chunk", error=exc) from exc
        if not chunks:
            raise _StepFailure(step="chunk", error=ValueError("no chunks generated from markdown"))
        self._mark_suspected_injection(chunks)
        self._log_event(run_id, source, "chunk_done", elapsed_ms=self._elapsed_ms(t0), num_chunks=len(chunks))

        document = self._build_document(source=source, markdown=parsed.markdown, metadata=merged_meta, chunks=chunks)
        try:
            deps.rag.add_document(document)
        except Exception as exc:
            raise _StepFailure(step="index", error=exc) from exc
        self._log_event(run_id, source, "index_done", elapsed_ms=self._elapsed_ms(t0), num_chunks=len(chunks))

        try:
            self._save_markdown(source.id, parsed.markdown, processed_dir)
        except Exception as exc:
            raise _StepFailure(step="persist", error=exc) from exc
        self._log_event(run_id, source, "persist_done", elapsed_ms=self._elapsed_ms(t0))

    def _get_pipeline_ingestor(self, source_kind: str) -> PipelineIngestorProtocol:
        ingestor = self._dispatcher.get_ingestor(source_kind)
        return ingestor  # type: ignore[return-value]

    @staticmethod
    def _build_default_dispatcher(fetcher: FetcherProtocol) -> IngestionDispatcher:
        pdf_parser = PdfMarkdownParser(pdf_processor=PDFProcessor())
        html_parser = HtmlMarkdownParser()
        enricher = MarkdownEnricher()
        ingestors = {
            SourceType.PDF: PdfIngestor(parser=pdf_parser, enricher=enricher, fetcher=fetcher),  # legacy compat
            SourceType.HTML: HtmlIngestor(parser=html_parser, enricher=enricher, fetcher=fetcher),  # legacy compat
        }
        parsers = {
            SourceType.PDF: pdf_parser,
            SourceType.HTML: html_parser,
        }
        return IngestionDispatcher(ingestors=ingestors, parsers=parsers)

    @staticmethod
    def _merge_metadata(source: SourceItem, fetched: Any, parsed_meta: dict[str, Any], enriched: Any) -> dict[str, Any]:
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

    @staticmethod
    def _build_document(source: SourceItem, markdown: str, metadata: dict[str, Any], chunks: list[Chunk]) -> Document:
        return Document(
            id=source.id,
            company_name=metadata.get("company_name", "unknown"),
            num_chunks=len(chunks),
            text=markdown,
            chunks=chunks,
            metadata=metadata,
        )

    @staticmethod
    def _mark_suspected_injection(chunks: list[Chunk]) -> None:
        for chunk in chunks:
            text = chunk.text or ""
            suspected = any(pattern.search(text) for pattern in INJECTION_PATTERNS)
            chunk.metadata["suspected_injection"] = suspected

    @staticmethod
    def _save_markdown(source_id: str, markdown: str, processed_dir: str) -> None:
        folder = Path(processed_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{source_id}.md").write_text(markdown, encoding="utf-8")

    @staticmethod
    def _already_ingested(deps: Any, source_id: str) -> bool:
        data = deps.rag.rag.collection.get(where={"source_id": source_id}, limit=1)
        ids = data.get("ids") or []
        return len(ids) > 0

    @staticmethod
    def _elapsed_ms(t0: float) -> int:
        return int((time.time() - t0) * 1000)

    @staticmethod
    def _log_event(run_id: str, source: SourceItem, step: str, **extra: Any) -> None:
        event = {"run_id": run_id, "source_id": source.id, "kind": source.kind, "url": str(source.url), "step": step}
        event.update(extra)
        logger.info("ingestion_event=%s", json.dumps(event, ensure_ascii=False))


def run_sources(sources: list[SourceItem], deps: Any, processed_dir: str = "data/processed") -> dict[str, Any]:
    """Wrapper de compatibilidade para o runner de ingestao."""
    return IngestionRunner(processed_dir=processed_dir).run_sources(sources=sources, deps=deps, processed_dir=processed_dir)
