from fastapi import APIRouter, Depends, HTTPException

from app.schemas.schemas import IngestionRequest, IngestResponse
from app.services.ingestion_service import IngestionService
from app.core.deps import get_deps

ingest_router = APIRouter()

@ingest_router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestionRequest, deps=Depends(get_deps)) -> IngestResponse:
    try:
        service = IngestionService(deps)
        if req.urls:
            raise HTTPException(status_code=501, detail="Ingest por URL ainda não implementado. Envie sem urls.")
        return service.ingest()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))