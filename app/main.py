import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings

from app.schemas.schemas import HealthResponse, IngestResponse, QueryResponse, QueryRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

_workflow_app = None
_deps = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _workflow_app, _deps
    from app.ai.workflows.workflow_dependencies import WorkflowDependencies
    from app.ai.workflows.workflow import build_workflows

    logger.info("Initializing workflow dependencies...")
    _deps = WorkflowDependencies.get_instance()
    _workflow_app = build_workflows(_deps)
    logger.info(
        "Workflow ready. Collection has %d chunks.",
        _deps.rag.collection.count(),
    )
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Financial Multi-Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health", response_model=HealthResponse)
def health():
    count = _deps.rag.collection.count() if _deps else 0
    return HealthResponse(
        status="ok",
        chunks_indexed=count,
        model=settings.MODEL_NAME,
    )

@app.post("/ingest", response_model=IngestResponse)
def ingest():
    """Parse all PDFs in DATA_DIR and upsert into ChromaDB."""
    from app.rag.pdf_processor import PDFProcessor

    processor = PDFProcessor(chunk_size=1200, chunk_overlap=150)
    docs = processor.parse_folder(settings.DATA_DIR)

    total_chunks = 0
    for doc in docs:
        _deps.rag.upsert(doc.chunks)
        total_chunks += len(doc.chunks)
        logger.info("Ingested %s → %d chunks", doc.metadata.get("filename"), len(doc.chunks))

    return IngestResponse(
        documents_processed=len(docs),
        total_chunks=total_chunks,
    )

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):

    from app.ai.workflows.workflow import create_initial_state

    if _workflow_app is None:
        raise HTTPException(status_code=503, detail="Workflow not initialized")

    initial_state = create_initial_state(req.query, company_catalog=_deps.company_catalog)

    t0 = time.time()
    final_state = None
    for event in _workflow_app.stream(initial_state):
        for _node_name, st in event.items():
            final_state = st
    elapsed = round(time.time() - t0, 2)

    if final_state is None:
        raise HTTPException(status_code=500, detail="Workflow produced no output")

    raw_citations = final_state.get("citations") or []
    citations = [
        c.model_dump() if hasattr(c, "model_dump") else c
        for c in raw_citations
    ]

    return QueryResponse(
        answer=final_state.get("final_answer"),
        confidence=final_state.get("confidence", 0.0),
        citations=citations,
        extracted_metrics=final_state.get("extracted_metrics"),
        sentiment_analysis=final_state.get("sentiment_analysis"),
        routing={
            "selected_agents": final_state.get("selected_agents", []),
            "reasoning": final_state.get("routing_reasoning", ""),
        },
        trace=final_state.get("agent_trace", []),
    )