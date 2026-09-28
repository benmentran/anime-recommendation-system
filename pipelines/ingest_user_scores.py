"""Ingest AniList user anime scores -> user_scores (PART A, real CF data).

Why AniList (not Jikan): Jikan's /users/* endpoints went 504 before the
2026-10-01 shutdown (catalog endpoints still 200). AniList GraphQL gives
scores in the user's own format PLUS real completedAt dates — strictly better
than Jikan (which carries no timestamps at all).

Schema: user_id = AniList username (TEXT), anime_id = idMal (matches
anime_catalog.mal_id; entries without idMal are skipped).

Usage:
    DATABASE_URL=... python pipelines/ingest_user_scores.py --users RebelPanda,Archaeon
    DATABASE_URL=... python pipelines/ingest_user_scores.py --users-file seeds.txt [--limit-users N]

Rate: ~1 request / 1.5 s (AniList allows 90/min). Resumable via
data/raw/user_score_users.txt (usernames done).
Deps: httpx, asyncpg. No mlflow/dvc.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")
DONE_FILE = Path("data/raw/user_score_users.txt")
ANILIST = "https://graphql.anilist.co"
STATUSES = ("COMPLETED", "CURRENT", "PAUSED", "DROPPED")

USER_Q = "query ($n: String) { User(name: $n) { mediaListOptions { scoreFormat } } }"
LIST_Q = """query ($n: String, $s: MediaListStatus) {
  MediaListCollection(userName: $n, type: ANIME, status: $s) {
    lists { entries { media { idMal } score
      completedAt { year month day } } } } }"""


def normalize_score(score, fmt: str):
    """Any AniList scoreFormat -> int 1..10. None/0 -> None (skip)."""
    if not score:
        return None
    try:
        if fmt == "POINT_100":
            v = round(float(score) / 10)
        elif fmt == "POINT_10_DECIMAL":
            v = round(float(score))
        elif fmt == "POINT_5":
            v = int(float(score) * 2)
        elif fmt == "POINT_3":
            v = {1: 3, 2: 6, 3: 10}.get(int(score))
            return v
        else:  # POINT_10
            v = int(score)
    except (TypeError, ValueError):
        return None
    return v if v and 1 <= v <= 10 else None


def fuzzy_to_ts(fz, fallback):
    """{year,month,day} (nones allowed) -> datetime.date; null -> fallback.

    Returns a date object (not str): asyncpg binds dates natively, while a
    str bind fails even with a ::timestamptz cast in SQL.
    """
    import datetime as _dt

    if not fz or not fz.get("year"):
        if isinstance(fallback, str):
            fallback = _dt.date.fromisoformat(fallback)
        return fallback
    return _dt.date(int(fz["year"]), int(fz.get("month") or 1), int(fz.get("day") or 1))


def parse_entries(payload: dict, username: str, fmt: str, now: str):
    """MediaListCollection payload -> rows(user_id, anime_id, score, scored_at). Pure."""
    out = []
    lists = ((payload.get("data") or {}).get("MediaListCollection") or {}).get("lists") or []
    for lst in lists:
        for e in lst.get("entries") or []:
            media = e.get("media") or {}
            mal = media.get("idMal")
            score = normalize_score(e.get("score"), fmt)
            if not mal or not score:
                continue
            out.append({"user_id": username, "anime_id": int(mal), "score": score,
                        "scored_at": fuzzy_to_ts(e.get("completedAt"), now)})
    return out


async def ingest_usernames(usernames: list[str], statuses=STATUSES[:2],
                           limit_users: "int | None" = None) -> dict:
    """Fetch + upsert scores. Returns {users_done, rows_upserted}."""
    import asyncpg
    import httpx

    force = os.getenv("SCORES_FORCE") == "1"
    done = set() if force else (
        set(DONE_FILE.read_text(encoding="utf-8").split()) if DONE_FILE.exists() else set())
    todo = [u for u in usernames if u not in done]
    if limit_users:
        todo = todo[:limit_users]
    pool = await asyncpg.connect(DATABASE_URL)
    users_done = rows = 0
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for u in todo:
                r = await client.post(ANILIST, json={"query": USER_Q,
                                                     "variables": {"n": u}})
                r.raise_for_status()
                user = (r.json().get("data") or {}).get("User")
                if not user:
                    print(f"user {u}: not found, skipped", flush=True)
                    continue
                fmt = (user.get("mediaListOptions") or {}).get("scoreFormat") or "POINT_10"
                import datetime as _dt
                now = _dt.date.today()  # noqa: DTZ011 - date (not datetime), no tz needed
                entries = []
                for st in statuses:
                    await asyncio.sleep(1.5)  # stay far under 90 req/min
                    rr = await client.post(ANILIST, json={
                        "query": LIST_Q, "variables": {"n": u, "s": st}})
                    rr.raise_for_status()
                    entries += parse_entries(rr.json(), u, fmt, now)
                if entries:
                    await pool.executemany(
                        """INSERT INTO user_scores (user_id, anime_id, score, scored_at)
                           VALUES ($1, $2, $3, $4)
                           ON CONFLICT (user_id, anime_id) DO UPDATE
                           SET score = EXCLUDED.score""",
                        [(e["user_id"], e["anime_id"], e["score"], e["scored_at"])
                         for e in entries])
                    rows += len(entries)
                users_done += 1
                DONE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(DONE_FILE, "a", encoding="utf-8") as f:  # noqa: ASYNC230 - KB checkpoint append
                    f.write(u + "\n")
                print(f"user {u}: {len(entries)} scored entries (fmt={fmt})", flush=True)
    finally:
        await pool.close()
    print(f"USERS_DONE users={users_done} rows_upserted~{rows}", flush=True)
    return {"users_done": users_done, "rows_upserted": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="")
    ap.add_argument("--users-file", default="")
    ap.add_argument("--statuses", default="COMPLETED,CURRENT")
    ap.add_argument("--limit-users", type=int, default=None)
    args = ap.parse_args()
    names = [u.strip() for u in args.users.split(",") if u.strip()]
    if args.users_file:
        with open(args.users_file, encoding="utf-8") as f:
            names += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not names:
        try:
            import yaml
            with open("params.yaml", encoding="utf-8") as _pf:
                cfg = yaml.safe_load(_pf) or {}
            names = list(((cfg.get("pipelines") or {}).get("cf") or {}).get("seed_users") or [])
        except Exception:  # noqa: BLE001 - optional config
            names = []
    if not names:
        raise SystemExit("no users: --users, --users-file, or params pipelines.cf.seed_users")
    asyncio.run(ingest_usernames(names, tuple(s.strip() for s in args.statuses.split(",")),
                                 args.limit_users))


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
