"""Anime crawl pipeline: skip-when-fresh, append NDJSON + checkpoint, batch upsert 500.

Usage: DATABASE_URL=... python -m pipelines.collection 1 2 3
(Airflow: from pipelines.collection import crawl)
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

from services.anime_service.clients.jikan_client import JikanClient

DATA_DIR = Path("data/raw")
OUT = DATA_DIR / "anime_jikan.ndjson"
CHECKPOINT = DATA_DIR / "crawled_ids.txt"
BATCH = 500


def _load_checkpoint() -> set[str]:
    if CHECKPOINT.exists():
        return set(CHECKPOINT.read_text().split())
    return set()


async def _fresh_ids(pool: asyncpg.Pool, ids: list[int]) -> set[int]:
    # ponytail: one SELECT ANY($1) instead of N SELECTs
    rows = await pool.fetch(
        "SELECT mal_id FROM anime_raw WHERE mal_id = ANY($1) AND expires_at > NOW()",
        ids,
    )
    return {r["mal_id"] for r in rows}


async def _upsert_raw(pool: asyncpg.Pool, rows: list[tuple]):
    await pool.executemany(
        """INSERT INTO anime_raw (mal_id, source, payload, fetched_at, expires_at)
           VALUES ($1, 'jikan', $2, $3, $4) ON CONFLICT (mal_id) DO NOTHING""",
        rows,
    )


async def crawl(mal_ids: list[int]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = _load_checkpoint()
    try:
        pool = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime"))
    except Exception:
        pool = None  # offline: crawl to NDJSON only
    try:
        fresh = await _fresh_ids(pool, mal_ids) if (pool is not None and mal_ids) else set()
    except Exception:
        fresh = set()
        pool = None
    todo = [i for i in mal_ids if str(i) not in done and i not in fresh]
    print(f"skip fresh={len(fresh)} checkpoint={len(done & set(map(str, mal_ids)))} todo={len(todo)}")

    client = JikanClient()
    buf: list[tuple] = []
    try:
        with open(OUT, "a", encoding="utf-8") as f, open(CHECKPOINT, "a", encoding="utf-8") as cp:
            for mal_id in todo:
                try:
                    data, expires = await client.get_anime_full(mal_id)
                except Exception as e:
                    print(f"skip {mal_id}: {e}")
                    continue
                f.write(json.dumps({"mal_id": mal_id, "data": data}, ensure_ascii=False) + "\n")
                cp.write(f"{mal_id}\n")
                cp.flush()
                buf.append((mal_id, json.dumps(data), datetime.now(timezone.utc), expires))
                if len(buf) >= BATCH and pool is not None:
                    await _upsert_raw(pool, buf)
                    buf.clear()
            if buf and pool is not None:
                await _upsert_raw(pool, buf)
    finally:
        await client.close()
        if pool is not None:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(crawl([int(a) for a in sys.argv[1:]]))
