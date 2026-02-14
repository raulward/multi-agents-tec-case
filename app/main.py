# app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import health, ingest, query
from app.core.logging_config import setup_logging

from app.ai.workflows.workflow import build_workflows
from app.ai.workflows.workflow_dependencies import WorkflowDependencies

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    

    logger.info("Initializing workflow dependencies...")
    deps = WorkflowDependencies.get_instance()
    workflow_app = build_workflows(deps)

    app.state.deps = deps
    app.state.workflow_app = workflow_app

    logger.info("Workflow ready. Collection has %d chunks.", deps.rag.count_chunks())
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Multi-Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.health_router, prefix="/v1", tags=["health"])
app.include_router(query.query_router, prefix="/v1", tags=["query"])
app.include_router(ingest.ingest_router, prefix="/v1", tags=["ingest"])
