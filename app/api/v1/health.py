# app/api/v1/health.py
from fastapi import APIRouter, Depends

from app.schemas.schemas import HealthResponse
from app.core.config import settings
from app.core.deps import get_deps

health_router = APIRouter()

@health_router.get("/health", response_model=HealthResponse)
def health(deps=Depends(get_deps)) -> HealthResponse:
    count = deps.rag.collection.count() if deps else 0
    return HealthResponse(
        status="ok",
        chunks_indexed=count,
        model=settings.MODEL_NAME,
    )