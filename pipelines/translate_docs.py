"""Translate EN retrieval docs -> Vietnamese (gpt-4o-mini), store doc_vi.

Resumable via data/raw/translate_ids.txt (mal_ids done). Skips rows that
already have doc_vi. Concurrency capped (semaphore) for rate-limit safety.

Usage: OPENAI_API_KEY=... DATABASE_URL=... python pipelines/translate_docs.py [--limit N]
Env: TRANSLATE_MODEL (default gpt-4o-mini).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
from openai import AsyncOpenAI

from pipelines.rag_docs import build_document

DATA_DIR = Path("data/raw")
DONE_FILE = DATA_DIR / "translate_ids.txt"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")
TRANSLATE_MODEL = os.getenv("TRANSLATE_MODEL", "gpt-4o-mini")
FETCH = 500
CONCURRENCY = 8

SYSTEM = (
    "Translate the following anime description from English to Vietnamese. "
    "Keep all proper names (titles, studios, character names), numbers, scores, "
    "years and genre/tag names EXACTLY as they are — translate only the "
    "descriptive prose (labels like Title/Genres/Synopsis stay in English). "
    "Return ONLY the translated document, no commentary."
)


def _row_to_en(r: dict) -> str:
    genres = r["genres"]
    if isinstance(genres, str):
        try:
            genres = json.loads(genres)
        except ValueError:
            genres = []
    studios = r["studios"]
    if isinstance(studios, str):
        try:
            studios = json.loads(studios)
        except ValueError:
            studios = []
    tags = r.get("tags_anilist")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except ValueError:
            tags = []
    return build_document({**r, "genres": genres, "studios": studios,
                           "tags_anilist": tags or []})


async def _translate_one(oai: AsyncOpenAI, sem: asyncio.Semaphore, text: str) -> str:
    async with sem:
        r = await oai.chat.completions.create(
            model=TRANSLATE_MODEL,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": text}],
            temperature=0.0, max_tokens=2000)
        return (r.choices[0].message.content or "").strip()


async def main(limit: int | None = None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = set(DATA_DIR.joinpath("translate_ids.txt").read_text().split()) \
        if DONE_FILE.exists() else set()
    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)
    pool = await asyncpg.connect(DATABASE_URL)
    try:
        cur = await pool.fetch(
            "SELECT mal_id, title, title_japanese, synopsis, episodes, status,"
            " season, year, studios, source, genres, score, tags_anilist"
            " FROM anime_catalog WHERE doc_vi IS NULL ORDER BY mal_id")
        todo = [dict(r) for r in cur if str(r["mal_id"]) not in done]
        if limit:
            todo = todo[:limit]
        print(f"to_translate={len(todo)}", flush=True)
        with open(DONE_FILE, "a", encoding="utf-8") as cp:
            for i in range(0, len(todo), FETCH):
                chunk = todo[i:i + FETCH]
                texts = [_row_to_en(r) for r in chunk]
                vis = await asyncio.gather(
                    *[_translate_one(oai, sem, t) for t in texts])
                await pool.executemany(
                    "UPDATE anime_catalog SET doc_vi = $2, updated_at = NOW()"
                    " WHERE mal_id = $1",
                    [(r["mal_id"], v) for r, v in zip(chunk, vis) if v])
                for r, v in zip(chunk, vis):
                    if v:
                        cp.write(f"{r['mal_id']}\n")
                        done.add(str(r["mal_id"]))
                cp.flush()
                print(f"translated={len(done)}", flush=True)
    finally:
        await pool.close()
    print("TRANSLATE_DONE", flush=True)


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    asyncio.run(main(lim))
