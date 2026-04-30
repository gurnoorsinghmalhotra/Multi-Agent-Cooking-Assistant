"""API routes for the cooking assistant."""

from fastapi import APIRouter, HTTPException

from app.schemas.request import QueryRequest
from app.schemas.response import QueryResponse
from app.services.orchestrator import handle_query

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Accept a natural language cooking query and return structured agent output."""
    try:
        return await handle_query(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
