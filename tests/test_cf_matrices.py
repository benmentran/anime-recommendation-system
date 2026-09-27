"""CF without mlflow: ratings adapter, matrix round-trip, endpoint fallback (no DB)."""
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from pipelines.model_dev import ContentBasedFiltering, ItemBasedCF, UserBasedCF
from scripts.build_cf_matrices import item_feature_frame, status_frame
from services.recommend_service import model_loader as ml_module
from services.recommend_service.model_loader import ModelLoader
from services.recommend_service.routers import recommend_router
from services.recommend_service.schemas.recommend_request import RecommendRequest


def _ratings():
    # users 1,2 love item 10; user 2 also loves 20 -> user 1 should get 20
    return [{"user_id": 1, "anime_id": 10, "status": "completed", "score": None},
            {"user_id": 2, "anime_id": 10, "status": "completed", "score": None},
            {"user_id": 2, "anime_id": 20, "status": "completed", "score": None},
            {"user_id": 3, "anime_id": 30, "status": "dropped", "score": None}]


def test_status_frame_prefers_explicit_score_and_drops_zero():
    df = status_frame(_ratings())
    assert set(df["item_id"]) == {10, 20}  # dropped item 30 excluded
    assert df["rating"].tolist() == [1.0, 1.0, 1.0]
    df2 = status_frame([{"user_id": 1, "anime_id": 7, "status": "watching", "score": 8}])
    assert df2.iloc[0]["rating"] == 0.8


def test_user_cf_recommends_friends_item(tmp_path):
    df = status_frame(_ratings())
    matrix = df.pivot(index="user_id", columns="item_id", values="rating")
    matrix.to_pickle(tmp_path / "user_item_matrix.pkl")
    m = UserBasedCF()
    m.train(str(tmp_path / "user_item_matrix.pkl"))
    recs = dict(m.recommend(1, 5))
    assert 20 in recs and 10 not in recs  # 10 already watched


def test_item_cf_and_content_based(tmp_path):
    df = status_frame(_ratings())
    matrix = df.pivot(index="user_id", columns="item_id", values="rating")
    matrix.to_pickle(tmp_path / "user_item_matrix.pkl")
    m = ItemBasedCF()
    m.train(str(tmp_path / "user_item_matrix.pkl"))
    assert isinstance(dict(m.recommend(1, 5)), dict)

    feats, vocab = item_feature_frame([
        {"mal_id": 10, "genres": ["Action"], "tags_anilist": [{"name": "Mecha", "weight": 90}]},
        {"mal_id": 20, "genres": ["Action"], "tags_anilist": [{"name": "Mecha", "weight": 80}]},
        {"mal_id": 30, "genres": ["Romance"], "tags_anilist": []}])
    assert "Mecha" in vocab and len(feats) == 3
    c = ContentBasedFiltering()
    c.train(feats, None)  # no reviews table for anime
    assert 20 in c.recommend(10, top_k=2)


def test_endpoints_use_local_models_and_fallback(monkeypatch, tmp_path):
    df = status_frame(_ratings())
    matrix = df.pivot(index="user_id", columns="item_id", values="rating")
    matrix.to_pickle(tmp_path / "user_item_matrix.pkl")
    for cls, name in ((UserBasedCF, "user_cf.pkl"), (ItemBasedCF, "item_cf.pkl")):
        m = cls()
        m.train(str(tmp_path / "user_item_matrix.pkl"))
        with open(tmp_path / name, "wb") as f:
            pickle.dump(m, f)
    feats, _ = item_feature_frame([
        {"mal_id": 10, "genres": ["Action"], "tags_anilist": []},
        {"mal_id": 20, "genres": ["Action"], "tags_anilist": []}])
    c = ContentBasedFiltering()
    c.train(feats, None)
    with open(tmp_path / "content_cf.pkl", "wb") as f:
        pickle.dump(c, f)
    with open(tmp_path / "popular.pkl", "wb") as f:
        pickle.dump([10, 20], f)

    loader = ModelLoader(str(tmp_path))
    loader.load_local()
    monkeypatch.setattr(recommend_router, "model_loader", loader)

    r = recommend_router.recommend_user_based(RecommendRequest(user_id=1, k=2))
    assert r["recommendations"] == [20]
    r = recommend_router.recommend_content_based(RecommendRequest(movie_id=10, top_k=2))
    assert 20 in r["recommendations"]
    r = recommend_router.recommend_for_you(user_id=1, k=2)
    assert set(r["recommendations"]) <= {10, 20} and len(r["recommendations"]) == 2
    r = recommend_router.recommend_for_you(user_id=None, k=2)  # cold user
    assert r["recommendations"] == [10, 20]

    # empty model dir -> popularity empty -> 503
    loader2 = ModelLoader(str(tmp_path / "empty"))
    loader2.load_local()
    monkeypatch.setattr(recommend_router, "model_loader", loader2)
    try:
        recommend_router.recommend_for_you(user_id=None, k=2)
        raised = False
    except Exception as e:
        raised = getattr(e, "status_code", None) == 503
    assert raised
    assert ml_module.ModelLoader is ModelLoader  # import sanity
