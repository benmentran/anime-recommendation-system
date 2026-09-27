"""Execute a db/*.sql migration file and print catalog stats.

Usage: DATABASE_URL=... python scripts/run_sql_file.py db/003_multisource.sql
"""
import asyncio
import os
import sys

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")


async def main(path: str):
    sql = open(path, encoding="utf-8").read()
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(sql)
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='anime_catalog' ORDER BY 1")
        print("COLS:", [r["column_name"] for r in cols], flush=True)
        row = await conn.fetchrow(
            "SELECT COUNT(*) n, COUNT(score_mal) sm, "
            "COUNT(*) - COUNT(image_url) noimg FROM anime_catalog")
        print(dict(row), flush=True)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
