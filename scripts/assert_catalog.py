"""Post-transform quality gate: fail (exit 1) when the catalog regresses.

Checks (thresholds = contract, set just above current healthy levels):
  row_count > 0 | title null = 0 | image_url null <= 5%
  score null <= 10% | year null <= 5%
Usage: DATABASE_URL=... python scripts/assert_catalog.py [--min-rows N]
Airflow calls main() as the task after transform (DAG fails on exception).
"""
import asyncio
import os
import sys

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")

THRESHOLDS = {"title": 0.0, "image_url": 0.05, "score": 0.10, "year": 0.05}


def evaluate(total: int, nulls: dict[str, int]) -> list[str]:
    """Pure: return failure messages (empty = pass)."""
    failures = []
    if total <= 0:
        return ["row_count is 0"]
    for col, max_rate in THRESHOLDS.items():
        rate = nulls.get(col, 0) / total
        if rate > max_rate:
            failures.append(f"{col} null-rate {rate:.3f} > {max_rate}")
    return failures


async def main(min_rows: int = 0) -> None:
    import asyncpg

    pool = await asyncpg.connect(DATABASE_URL)
    try:
        row = await pool.fetchrow(
            """SELECT COUNT(*) total,
                      COUNT(*) - COUNT(title) AS title,
                      COUNT(*) - COUNT(image_url) AS image_url,
                      COUNT(*) - COUNT(score) AS score,
                      COUNT(*) - COUNT(year) AS year
               FROM anime_catalog""")
        total = row["total"]
        print(f"rows={total}", flush=True)
        if total < min_rows:
            raise SystemExit(f"FAIL: rows {total} < min_rows {min_rows}")
        failures = evaluate(total, dict(row))
        for f_ in failures:
            print(f"FAIL: {f_}", flush=True)
        if failures:
            raise SystemExit(1)
        print("ASSERT_OK", flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--min-rows") + 1]) if "--min-rows" in sys.argv else 0
    asyncio.run(main(lim))
