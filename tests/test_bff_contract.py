"""BFF JSON contract: health + router prefixes, no Jinja2."""
import sys

sys.path.insert(0, ".")
from fastapi.testclient import TestClient

from services.web_service.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_api_prefixes_registered():
    paths = {r.path for r in app.routes}
    assert "/api/v1/anime/trending" in paths
    assert "/api/v1/list" in paths


def test_no_jinja_in_app():
    src = open("services/web_service/app.py").read()
    assert "Jinja2" not in src and "TemplateResponse" not in src


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Captures SQL text + params, returns canned rows (no live DB)."""

    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = {}

    async def execute(self, stmt, params=None):
        self.sql = str(stmt)
        self.params = dict(params or {})
        return _Rows(self.rows)


def _override(rows):
    from types import SimpleNamespace

    from services.web_service.db import get_session

    fake = _FakeSession([SimpleNamespace(**r) for r in rows])

    async def _get():
        yield fake

    app.dependency_overrides[get_session] = _get
    return fake


def test_genres_returns_name_count():
    from services.web_service.db import get_session

    fake = _override([{"name": "Action", "count": 3}, {"name": "Comedy", "count": 2}])
    try:
        r = client.get("/api/v1/anime/genres")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert r.status_code == 200
    assert r.json() == [{"name": "Action", "count": 3}, {"name": "Comedy", "count": 2}]
    assert "GROUP BY" in fake.sql


def test_search_accepts_season_status_and_orders_by_score():
    from services.web_service.db import get_session

    fake = _override([{
        "mal_id": 5114, "title": "FMA:B", "title_japanese": None,
        "image_url": "https://cdn.example/fma.jpg", "score": 9.11, "year": 2009,
    }])
    try:
        r = client.get("/api/v1/anime/search", params={
            "q": "", "genre": "Action", "year": 2009,
            "season": "spring", "status": "Finished Airing",
        })
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert r.status_code == 200
    assert r.json()[0]["id"] == 5114
    assert ":season" in fake.sql and ":status" in fake.sql
    assert "ORDER BY score DESC NULLS LAST" in fake.sql
    assert fake.params["season"] == "spring"
    assert fake.params["status"] == "Finished Airing"
