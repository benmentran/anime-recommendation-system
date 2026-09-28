"""ID discovery for the anime crawl: top-ranked + seasonal + manual.

Sources (user-approved):
  1. /top/anime paginated, up to TOP_LIMIT (default 5000) — classics, crawl once.
  2. Current season + next 2 seasons (/seasons/now, /seasons/{year}/{season}) — fresh, every run.
  3. Manual IDs (DAG conf / CLI) — ad-hoc additions.

Usage: DATABASE_URL=... python -m pipelines.discovery  (prints IDs)
(Airflow: from pipelines.discovery import discover_all)
"""
import asyncio
import sys
from datetime import date

from services.anime_service.clients.anilist_client import fetch_top_mal_ids

SEASONS = ("winter", "spring", "summer", "fall")
TOP_LIMIT = 5000
TOP_ENDPOINT = "/top/anime"  # Jikan fallback only (list endpoints 504 intermittently)


def season_for(month: int) -> int:
    return min((month - 1) // 3, 3)


def current_and_next_seasons(today: date | None = None, n: int = 3) -> list[tuple[int, str]]:
    """Current season + next n-1. e.g. Sep 2026 -> [(2026,'fall'),(2026+1? no)...]."""
    today = today or date.today()
    idx = season_for(today.month)
    year = today.year
    out = []
    for _ in range(n):
        out.append((year, SEASONS[idx]))
        idx += 1
        if idx == 4:
            idx, year = 0, year + 1
    return out


async def _paged_ids(client, endpoint: str, limit: int) -> list[int]:
    """Collect mal_id from a paginated Jikan list endpoint, in order, up to limit."""
    ids: list[int] = []
    seen: set[int] = set()
    page = 1
    while len(ids) < limit:
        body = await client.get_list(endpoint, {"page": page})
        data = body.get("data", [])
        if not data:
            break
        for item in data:
            mid = item.get("mal_id")
            if mid is not None and mid not in seen and len(ids) < limit:
                seen.add(mid)
                ids.append(mid)
        pagination = body.get("pagination", {})
        if not pagination.get("has_next_page", False):
            break
        page += 1
        if page > pagination.get("last_visible_page", page):
            break
    return ids


async def discover_top_ids(client, limit: int = TOP_LIMIT) -> list[int]:
    return await _paged_ids(client, TOP_ENDPOINT, limit)


async def discover_season_ids(client, year: int, season: str, limit: int = 1000) -> list[int]:
    return await _paged_ids(client, f"/seasons/{year}/{season}", limit)


async def discover_all(client=None, top_limit: int = TOP_LIMIT) -> list[int]:
    """Merge top + seasonal, deduped, top-first order.

    Primary: AniList GraphQL (Jikan list endpoints 504). Fallback: Jikan
    pagination (needs a JikanClient passed as `client`).
    """
    try:
        top = await fetch_top_mal_ids(top_limit)
        seen = set(top)
        out = list(top)
        for year, season in current_and_next_seasons():
            try:
                seasonal = await fetch_top_mal_ids(1000, season, year)
            except Exception as e:  # noqa: BLE001 - one bad season must not kill discovery
                print(f"season {year}/{season} skipped: {e}")
                continue
            for mid in seasonal:
                if mid not in seen:
                    seen.add(mid)
                    out.append(mid)
        return out
    except Exception as e:
        print(f"anilist discovery failed ({e}), falling back to jikan")
        if client is None:
            raise
        top = await discover_top_ids(client, top_limit)
        seen = set(top)
        out = list(top)
        for year, season in current_and_next_seasons():
            try:
                seasonal = await discover_season_ids(client, year, season)
            except Exception as se:  # noqa: BLE001
                print(f"season {year}/{season} skipped: {se}")
                continue
            for mid in seasonal:
                if mid not in seen:
                    seen.add(mid)
                    out.append(mid)
        return out


async def _main(argv: list[str]) -> None:
    limit = int(argv[0]) if argv else TOP_LIMIT
    ids = await discover_all(None, limit)
    print(f"discovered={len(ids)}")
    for mid in ids:
        print(mid)


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
