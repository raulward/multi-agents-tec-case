from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.deps import get_deps
from app.schemas.api import HealthResponse

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse)
def health(deps=Depends(get_deps)) -> HealthResponse:
    count = deps.rag.count_chunks() if deps else 0
    return HealthResponse(
        status="ok",
        chunks_indexed=count,
        model=settings.MODEL_NAME,
    )
