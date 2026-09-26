"""RAG ask: semantic retrieval (Qdrant) + generation (gpt-4o)."""
import os

import httpx
from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from pipelines.rag_prompt import build_messages
from pipelines.rag_retrieval import (
    build_qdrant_filter,
    detect_language,
    infer_genre_filter,
    rerank_hits,
)

router = APIRouter(prefix="/api/v1/rag")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
COLLECTION = os.getenv("COLLECTION", "anime")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")


class AskRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    k: int = Field(default=5, ge=1, le=10)


class Candidate(BaseModel):
    mal_id: int
    title: str
    score: float | None = None


class AskResponse(BaseModel):
    answer: str
    candidates: list[Candidate]


def _oai() -> AsyncOpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    return AsyncOpenAI(api_key=key)


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    oai = _oai()
    lang = detect_language(req.query)
    emb = await oai.embeddings.create(model=EMBED_MODEL, input=[req.query])
    genre = infer_genre_filter(req.query)
    qfilter = build_qdrant_filter(genre)
    # hybrid: genre prefilter (over-fetch for rerank room), fallback pure-vector
    fetch_k = min(req.k * 2, 10) if qfilter else req.k
    body: dict = {"vector": emb.data[0].embedding, "limit": fetch_k,
                  "with_payload": True}
    if qfilter:
        body["filter"] = qfilter
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{QDRANT_URL}/collections/{COLLECTION}/points/search"
        r = await client.post(url, json=body)
        if r.status_code == 400 and qfilter:
            # no full-text index for `genres` -> retry pure-vector
            body.pop("filter", None)
            body["limit"] = req.k
            r = await client.post(url, json=body)
        if r.status_code == 404:
            raise HTTPException(status_code=503, detail="vector index not built yet")
        r.raise_for_status()
        hits = r.json().get("result", [])
    hits = rerank_hits(hits)[:req.k]
    cands = [{"mal_id": h["payload"]["mal_id"], "title": h["payload"]["title"],
              "genres": h["payload"].get("genres"), "year": h["payload"].get("year"),
              "score": h["payload"].get("score"), "synopsis": h["payload"].get("synopsis")}
             for h in hits]
    chat = await oai.chat.completions.create(
        model=LLM_MODEL, messages=build_messages(req.query, cands, lang=lang),
        temperature=0.3, max_tokens=800)
    return {"answer": chat.choices[0].message.content or "",
            "candidates": [{"mal_id": c["mal_id"], "title": c["title"],
                            "score": c["score"]} for c in cands]}
