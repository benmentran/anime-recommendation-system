"""One-shot migrate of legacy TinyDB users.json -> Postgres users table.

Usage: DATABASE_URL=postgresql://anime:animepass@localhost:5432/anime python scripts/migrate_users_json.py [path/to/users.json]
Run once, verify row counts, then archive the json file. Exits 0 (no-op) if file missing.
"""
import asyncio
import json
import os
import sys

import asyncpg

SRC = sys.argv[1] if len(sys.argv) > 1 else "users.json"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")


def load_docs(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):  # TinyDB: {"_default": {"1": {...}}}
        table = data.get("_default", data)
        docs = list(table.values()) if isinstance(table, dict) else table
    else:
        docs = data
    return [d for d in docs if isinstance(d, dict) and d.get("email")]


async def main() -> None:
    if not os.path.exists(SRC):
        print(f"no {SRC}, nothing to migrate")
        return
    docs = load_docs(SRC)
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = [(d["email"], d.get("hashed_password") or d.get("password_hash") or "",
                 d.get("display_name"), d.get("google_id"), d.get("avatar_url"))
                for d in docs]
        await conn.executemany(
            """INSERT INTO users (email, password_hash, display_name, google_id, avatar_url)
               VALUES ($1, $2, $3, $4, $5) ON CONFLICT (email) DO NOTHING""", rows)
        print(f"migrated {len(rows)} users from {SRC}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
