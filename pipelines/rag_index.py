"""Offline: embed anime_catalog -> Qdrant (text-embedding-3-small, cosine/HNSW).

Resumable via data/raw/rag_indexed_ids.txt (mal_ids already upserted).
Uses raw httpx for Qdrant REST (qdrant-client needs ctypes, broken in WSL venv).

Usage: OPENAI_API_KEY=... DATABASE_URL=... QDRANT_URL=http://localhost:6333 \\
       python pipelines/rag_index.py [--limit N]
Env: EMBED_MODEL (default text-embedding-3-small), COLLECTION (default anime).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
import httpx
from openai import AsyncOpenAI

from pipelines.rag_docs import build_document

DATA_DIR = Path("data/raw")
DONE_FILE = DATA_DIR / "rag_indexed_ids.txt"
COLLECTION = os.getenv("COLLECTION", "anime")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")
EMBED_BATCH = 100
FETCH = 500


def _done() -> set[str]:
    if DONE_FILE.exists():
        return set(DONE_FILE.read_text().split())
    return set()


async def ensure_collection(client: httpx.AsyncClient):
    r = await client.get(f"{QDRANT_URL}/collections/{COLLECTION}")
    if r.status_code == 200:
        return
    r = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}",
        json={"vectors": {"size": EMBED_DIM, "distance": "Cosine"},
              "hnsw_config": {"m": 16, "ef_construct": 128}},
    )
    r.raise_for_status()
    print(f"collection {COLLECTION} created", flush=True)


async def main(limit: int | None = None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = _done()
    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    pool = await asyncpg.connect(DATABASE_URL)
    async with httpx.AsyncClient(timeout=60) as qd:
        await ensure_collection(qd)
        todo = 0
        capped = False
        async with pool.transaction():
            cur = await pool.cursor(
                "SELECT mal_id, title, title_japanese, synopsis, episodes, status,"
                " season, year, studios, source, genres, score, image_url"
                " FROM anime_catalog ORDER BY mal_id")
            with open(DONE_FILE, "a", encoding="utf-8") as cp:
                while True:
                    rows = await cur.fetch(FETCH)
                    if not rows:
                        break
                    fresh = [dict(r) for r in rows if str(r["mal_id"]) not in done]
                    for i in range(0, len(fresh), EMBED_BATCH):
                        chunk = fresh[i:i + EMBED_BATCH]
                        if limit:
                            chunk = chunk[:max(limit - todo, 0)]
                            if not chunk:
                                capped = True
                                break
                        texts = [build_document(r) for r in chunk]
                        emb = await oai.embeddings.create(model=EMBED_MODEL, input=texts)
                        points = []
                        for r, e in zip(chunk, emb.data):
                            genres = r["genres"]
                            if isinstance(genres, str):
                                genres = json.loads(genres)
                            points.append({
                                "id": r["mal_id"],
                                "vector": e.embedding,
                                "payload": {
                                    "mal_id": r["mal_id"], "title": r["title"],
                                    "genres": ", ".join(genres or []),
                                    "year": r["year"], "score": r["score"],
                                    "image_url": r["image_url"],
                                    "synopsis": (r["synopsis"] or "")[:1500],
                                }})
                        up = await qd.put(f"{QDRANT_URL}/collections/{COLLECTION}/points",
                                          params={"wait": "true"}, json={"points": points})
                        up.raise_for_status()
                        for r in chunk:
                            cp.write(f"{r['mal_id']}\n")
                            done.add(str(r["mal_id"]))
                        cp.flush()
                        todo += len(chunk)
                        print(f"indexed={todo}", flush=True)
                    if capped:
                        break
    await pool.close()
    print("LIMIT_REACHED" if capped else "INDEX_DONE", flush=True)


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    asyncio.run(main(lim))
