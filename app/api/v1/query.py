from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_deps, get_workflow
from app.schemas.api import QueryRequest, QueryResponse
from app.services.query_service import QueryService

query_router = APIRouter()


@query_router.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    deps=Depends(get_deps),
    workflow_app=Depends(get_workflow),
) -> QueryResponse:
    service = QueryService(workflow_app, deps)
    try:
        return service.run(req.query)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
