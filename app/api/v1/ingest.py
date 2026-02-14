from fastapi import APIRouter, Depends

from app.core.deps import get_deps
from app.schemas.api import IngestResponse, IngestionRequest
from app.services.ingestion_service import IngestionService

ingest_router = APIRouter()


@ingest_router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestionRequest, deps=Depends(get_deps)) -> IngestResponse:
    service = IngestionService(deps)
    return service.ingest(req)
