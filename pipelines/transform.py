"""Streaming transform fallback (only when SQL can't express it).

Uses server-side cursor + fetchmany(1000); never loads full file/table.
SQL-first path lives in db/002_transform.sql; Airflow: from pipelines.transform import main.
"""
import json
import os

import asyncpg

FETCH = 1000
UPSERT_BATCH = 500


async def transform_python_fallback(ndjson_path: str | None = None):
    pool = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime"))
    try:
        if ndjson_path:  # line-streamed, never json.load()
            buf = []
            with open(ndjson_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        buf.append(json.loads(line))
                        if len(buf) >= UPSERT_BATCH:
                            await _upsert(pool, buf)
                            buf.clear()
            if buf:
                await _upsert(pool, buf)
        else:  # DB cursor path
            async with pool.transaction():
                async for batch in _batches(pool):
                    await _upsert(pool, batch)
        await pool.execute("UPDATE etl_watermark SET last_run = NOW() WHERE pipeline = 'anime_transform'")
    finally:
        await pool.close()


async def _batches(pool: asyncpg.Pool):
    async with pool.transaction():
        cur = await pool.cursor("SELECT mal_id, payload FROM anime_raw WHERE fetched_at > "
                                "(SELECT last_run FROM etl_watermark WHERE pipeline='anime_transform')")
        while True:
            rows = await cur.fetch(FETCH)
            if not rows:
                return
            yield [{"mal_id": r["mal_id"], **(r["payload"] if isinstance(r["payload"], dict) else {})}
                   for r in rows]


async def _upsert(pool: asyncpg.Pool, rows: list[dict]):
    import json

    from services.anime_service.mappers import to_catalog

    def _raw(r: dict) -> dict:
        inner = r.get("data")  # NDJSON path stores {"mal_id","data"} wrapper
        return inner if isinstance(inner, dict) else r

    mapped = [to_catalog(r.get("mal_id"), _raw(r), None) for r in rows]
    await pool.executemany(
        """INSERT INTO anime_catalog
           (mal_id, title, title_japanese, synopsis, episodes, status, season, year,
            studios, source, genres, tags, score, image_url, updated_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,NOW())
           ON CONFLICT (mal_id) DO UPDATE SET
           title=EXCLUDED.title, title_japanese=EXCLUDED.title_japanese,
           synopsis=EXCLUDED.synopsis, episodes=EXCLUDED.episodes, status=EXCLUDED.status,
           season=EXCLUDED.season, year=EXCLUDED.year, studios=EXCLUDED.studios,
           source=EXCLUDED.source, genres=EXCLUDED.genres, tags=EXCLUDED.tags,
           score=EXCLUDED.score, image_url=EXCLUDED.image_url, updated_at=NOW()""",
        [(m["mal_id"], m["title"], m["title_japanese"], m["synopsis"], m["episodes"],
          m["status"], m["season"], m["year"], json.dumps(m["studios"]), m["source"],
          json.dumps(m["genres"]), json.dumps(m["tags"]), m["score"], m["image_url"])
         for m in mapped],
    )


async def main(ndjson_path: str | None = None):
    await transform_python_fallback(ndjson_path)


if __name__ == "__main__":
    import asyncio
    import sys

    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
