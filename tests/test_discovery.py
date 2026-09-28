"""ID discovery: season math + paged merge/dedupe (mocked client, no network)."""
import asyncio
import sys
from datetime import date
from unittest.mock import AsyncMock

sys.path.insert(0, ".")
from pipelines import discovery as disc


def test_season_math():
    assert disc.current_and_next_seasons(date(2026, 9, 25), 3) == [
        (2026, "summer"), (2026, "fall"), (2027, "winter")]  # anime seasons: Jul-Sep = summer
    assert disc.current_and_next_seasons(date(2026, 1, 15), 2) == [
        (2026, "winter"), (2026, "spring")]


def test_discover_all_merges_top_first_deduped(monkeypatch):
    async def fake_top(limit=5000, season=None, season_year=None):
        if season is None:
            return [1, 2, 3]
        return [3, 99]

    monkeypatch.setattr(disc, "fetch_top_mal_ids", fake_top)
    ids = asyncio.run(disc.discover_all(None, top_limit=10))
    assert ids[:3] == [1, 2, 3]  # top order kept
    assert ids.count(3) == 1  # deduped
    assert 99 in ids  # seasonal extras appended


def test_discover_all_falls_back_to_jikan(monkeypatch):
    async def boom(*a, **k):
        raise ConnectionError("anilist down")

    monkeypatch.setattr(disc, "fetch_top_mal_ids", boom)

    async def run():
        client = AsyncMock()

        async def fake_list(endpoint, params=None):
            page = (params or {}).get("page", 1)
            if endpoint == "/top/anime":
                if page == 1:
                    return {"data": [{"mal_id": 1}, {"mal_id": 2}],
                            "pagination": {"has_next_page": True, "last_visible_page": 2}}
                return {"data": [{"mal_id": 2}, {"mal_id": 3}],
                        "pagination": {"has_next_page": False, "last_visible_page": 2}}
            return {"data": [{"mal_id": 3}, {"mal_id": 99}],
                    "pagination": {"has_next_page": False, "last_visible_page": 1}}

        client.get_list.side_effect = fake_list
        return await disc.discover_all(client, top_limit=10)

    ids = asyncio.run(run())
    assert ids[:3] == [1, 2, 3]
    assert 99 in ids


def test_anilist_stops_before_depth_cap(monkeypatch):
    """AniList allows max 5000 entries depth: page 100 fetched, page 101 never requested."""
    import httpx as _httpx

    from services.anime_service.clients import anilist_client as ani

    requested = []

    class FakeResp:
        status_code = 200
        headers = {}
        text = "{}"

        def __init__(self, page):
            self._page = page

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"Page": {
                "pageInfo": {"hasNextPage": True},
                "media": [{"idMal": (self._page - 1) * 50 + i} for i in range(50)]}}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            requested.append(json["variables"]["page"])
            return FakeResp(json["variables"]["page"])

    monkeypatch.setattr(_httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    ids = asyncio.run(ani.fetch_top_mal_ids(6000))  # limit above depth cap
    assert max(requested) == 100
    assert 101 not in requested
    assert len(ids) == 5000


def test_paged_ids_stops_at_limit():
    async def run():
        client = AsyncMock()

        async def fake_list(endpoint, params=None):
            page = (params or {}).get("page", 1)
            base = (page - 1) * 25
            return {"data": [{"mal_id": base + i} for i in range(25)],
                    "pagination": {"has_next_page": True, "last_visible_page": 99}}

        client.get_list.side_effect = fake_list
        return await disc.discover_top_ids(client, limit=30)

    assert len(asyncio.run(run())) == 30
