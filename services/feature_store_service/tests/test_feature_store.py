"""Feature store contract: 6 anime-only /features routes, legacy routes gone."""
import re
import sys

sys.path.insert(0, ".")

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.feature_store_service.routers import features_router

app = FastAPI()
app.include_router(features_router.router)
client = TestClient(app)

ONLINE_PATHS = [
    "/features/online/users",
    "/features/online/movies",
    "/features/online/ratings",
]
HISTORICAL_PATHS = [
    "/features/historical/users",
    "/features/historical/movies",
    "/features/historical/ratings",
]


def test_six_anime_routes_registered():
    paths = {r.path for r in app.routes}
    for p in ONLINE_PATHS + HISTORICAL_PATHS:
        assert p in paths, p


def test_app_py_mounts_only_anime_routers():
    src = open("services/feature_store_service/app.py").read()
    mounted = sorted(set(re.findall(r"(\w+_router)\.router", src)))
    assert mounted == [
        "features_router",
        "movie_features_router",
        "rating_features_router",
        "user_features_router",
    ]


def test_online_routes_return_records(monkeypatch):
    monkeypatch.setattr(
        features_router, "get_user_features_online",
        lambda ids: pd.DataFrame([{"user_id": i} for i in ids]),
    )
    monkeypatch.setattr(
        features_router, "get_movie_features_online",
        lambda ids: pd.DataFrame([{"movie_id": i} for i in ids]),
    )
    monkeypatch.setattr(
        features_router, "get_rating_features_online",
        lambda u, m: pd.DataFrame([{"user_id": u[0], "item_id": m[0]}]),
    )
    r = client.post("/features/online/users", params={"user_ids": [1, 2]})
    assert [row["user_id"] for row in r.json()] == [1, 2]
    r = client.post("/features/online/movies", params={"movie_ids": [7]})
    assert r.json() == [{"movie_id": 7}]
    r = client.post(
        "/features/online/ratings", params={"user_ids": [1], "item_ids": [7]}
    )
    assert r.json() == [{"user_id": 1, "item_id": 7}]


def test_historical_routes_return_records(monkeypatch):
    monkeypatch.setattr(
        features_router, "get_user_features_df",
        lambda: pd.DataFrame([{"user_id": 1}]),
    )
    monkeypatch.setattr(
        features_router, "get_movie_features_df",
        lambda: pd.DataFrame([{"movie_id": 7}]),
    )
    monkeypatch.setattr(
        features_router, "get_rating_features_df",
        lambda: pd.DataFrame([{"rating": 5}]),
    )
    assert client.get("/features/historical/users").json() == [{"user_id": 1}]
    assert client.get("/features/historical/movies").json() == [{"movie_id": 7}]
    assert client.get("/features/historical/ratings").json() == [{"rating": 5}]
