"""Manual end-to-end RAG ask (mirrors routers/rag_router.ask). Usage: ... QUERY."""
import asyncio
import os
import sys

sys.path.insert(0, "/mnt/f/netflix-movie-recommendation-system")

import httpx
from openai import AsyncOpenAI

from pipelines.rag_prompt import build_messages
from pipelines.rag_retrieval import (
    build_qdrant_filter,
    detect_language,
    infer_genre_filter,
    rerank_hits,
)

QDRANT = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
COLLECTION = os.getenv("COLLECTION", "anime")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")


async def main(query: str, k: int = 5):
    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    lang = detect_language(query)
    emb = await oai.embeddings.create(model=EMBED_MODEL, input=[query])
    genre = infer_genre_filter(query)
    qfilter = build_qdrant_filter(genre)
    fetch_k = min(k * 2, 10) if qfilter else k
    body: dict = {"vector": emb.data[0].embedding, "limit": fetch_k,
                  "with_payload": True}
    if qfilter:
        body["filter"] = qfilter
    async with httpx.AsyncClient(timeout=30) as c:
        info = await c.get(f"{QDRANT}/collections/{COLLECTION}")
        print("POINTS:", info.json()["result"]["points_count"], flush=True)
        print(f"LANG: {lang} GENRE_FILTER: {genre}", flush=True)
        r = await c.post(f"{QDRANT}/collections/{COLLECTION}/points/search", json=body)
        if r.status_code == 400 and qfilter:
            body.pop("filter", None)
            body["limit"] = k
            r = await c.post(f"{QDRANT}/collections/{COLLECTION}/points/search", json=body)
        r.raise_for_status()
        hits = rerank_hits(r.json()["result"])[:k]
    cands = [{"mal_id": h["payload"]["mal_id"], "title": h["payload"]["title"],
              "genres": h["payload"].get("genres"), "year": h["payload"].get("year"),
              "score": h["payload"].get("score"),
              "synopsis": h["payload"].get("synopsis")} for h in hits]
    print("CANDIDATES:", [(c["title"], c["score"]) for c in cands], flush=True)
    chat = await oai.chat.completions.create(
        model=LLM_MODEL, messages=build_messages(query, cands, lang=lang),
        temperature=0.3, max_tokens=800)
    print("=" * 60)
    print(chat.choices[0].message.content)


asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5))
