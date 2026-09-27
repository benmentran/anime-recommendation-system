"""AniList enrichment: tags+rank, scores, description -> anime_catalog.

Fills the *_anilist columns created by db/003 (plus description_anilist,
created here idempotently). Resumable: skips rows whose sources already
contain 'anilist'. ~103 GraphQL calls for 5132 anime at 50 IDs/call.

Usage: DATABASE_URL=... python pipelines/anilist_enrich.py [--limit N]
"""
import asyncio
import json
import os
import re
import sys

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")
FETCH = 500


def strip_html(text: str | None, limit: int = 2000) -> str | None:
    """AniList descriptions are rich text (<br>, <i>); keep plain text."""
    if not text:
        return None
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:limit] or None


def to_row(media: dict) -> dict | None:
    """Raw AniList media -> catalog update mapping (pure, tested)."""
    mal_id = media.get("idMal")
    if mal_id is None:
        return None
    tags = [{"name": t.get("name"), "weight": t.get("rank") or 0}
            for t in (media.get("tags") or []) if t.get("name")]
    return {"mal_id": mal_id, "tags_anilist": tags,
            "score_anilist": (media.get("averageScore") or 0) / 10 or None,
            "favourites_anilist": media.get("favourites"),
            "popularity_anilist": media.get("popularity"),
            "description_anilist": strip_html(media.get("description"))}


async def main(limit: int | None = None):
    from services.anime_service.clients.anilist_client import fetch_media_batch

    pool = await asyncpg.connect(DATABASE_URL)
    try:
        await pool.execute(
            "ALTER TABLE anime_catalog ADD COLUMN IF NOT EXISTS "
            "description_anilist TEXT")
        cur = await pool.fetch(
            "SELECT mal_id FROM anime_catalog "
            "WHERE NOT (sources @> '{anilist}') ORDER BY mal_id")
        ids = [r["mal_id"] for r in cur]
        if limit:
            ids = ids[:limit]
        print(f"to_enrich={len(ids)}", flush=True)
        done = 0
        for i in range(0, len(ids), FETCH):
            chunk = ids[i:i + FETCH]
            try:
                media = await fetch_media_batch(chunk)
            except Exception as e:  # noqa: BLE001 - skip chunk, resume next run
                print(f"chunk@{i} failed: {e}", flush=True)
                continue
            rows = [r for m in media for r in [to_row(m)] if r]
            if rows:
                await pool.executemany(
                    """UPDATE anime_catalog SET
                         tags_anilist = $2::jsonb, score_anilist = $3,
                         favourites_anilist = $4, popularity_anilist = $5,
                         description_anilist = $6,
                         sources = (SELECT ARRAY(SELECT DISTINCT unnest(
                             sources || '{anilist}'))),
                         updated_at = NOW()
                       WHERE mal_id = $1""",
                    [(r["mal_id"], json.dumps(r["tags_anilist"]),
                      r["score_anilist"], r["favourites_anilist"],
                      r["popularity_anilist"], r["description_anilist"]) for r in rows])
            done += len(rows)
            print(f"enriched={done}", flush=True)
    finally:
        await pool.close()
    print("ENRICH_DONE", flush=True)


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    asyncio.run(main(lim))
