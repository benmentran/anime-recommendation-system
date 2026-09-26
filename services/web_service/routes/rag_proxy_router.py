"""BFF proxy for RAG ask -> recommend_service. Frontend calls :8000 only."""
import os

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


def _upstream() -> str:
    return os.getenv("RECOMMEND_URL", "http://localhost:8001").rstrip("/")


@router.post("/ask")
async def ask_proxy(req: Request):
    """Passthrough body {query, k} to recommend_service, keep {answer, candidates} shape."""
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{_upstream()}/api/v1/rag/ask", json=body)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"recommend_service unreachable: {e}")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()
