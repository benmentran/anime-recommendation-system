"""Feature lookup under /features (online + historical, anime scope).

Anime scope: only online/historical routes for user/movie/rating entities.
Legacy movie/TV routes were dropped (out of scope).
"""
from fastapi import APIRouter, Query
from typing import List

try:  # repo root / pytest / Airflow layout
    from services.feature_store_service.get_online_features import (
        get_user_features_online,
        get_movie_features_online,
        get_rating_features_online,
    )
    from services.feature_store_service.get_historical_features import (
        get_user_features_df,
        get_movie_features_df,
        get_rating_features_df,
    )
except ImportError:  # container layout (service dir is WORKDIR)
    from get_online_features import (
        get_user_features_online,
        get_movie_features_online,
        get_rating_features_online,
    )
    from get_historical_features import (
        get_user_features_df,
        get_movie_features_df,
        get_rating_features_df,
    )

router = APIRouter(prefix="/features", tags=["Features"])

# ---------------- ONLINE FEATURES ----------------
@router.post("/online/users")
def online_user_features(user_ids: List[int] = Query(...)):
    df = get_user_features_online(user_ids)
    return df.to_dict(orient="records")

@router.post("/online/movies")
def online_movie_features(movie_ids: List[int] = Query(...)):
    df = get_movie_features_online(movie_ids)
    return df.to_dict(orient="records")

@router.post("/online/ratings")
def online_rating_features(user_ids: List[int] = Query(...), item_ids: List[int] = Query(...)):
    df = get_rating_features_online(user_ids, item_ids)
    return df.to_dict(orient="records")


# ---------------- HISTORICAL FEATURES ----------------
@router.get("/historical/users")
def historical_user_features():
    df = get_user_features_df()
    return df.to_dict(orient="records")

@router.get("/historical/movies")
def historical_movie_features():
    df = get_movie_features_df()
    return df.to_dict(orient="records")

@router.get("/historical/ratings")
def historical_rating_features():
    df = get_rating_features_df()
    return df.to_dict(orient="records")
