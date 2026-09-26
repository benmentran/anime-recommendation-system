from fastapi import APIRouter, HTTPException
from feast import FeatureStore
from fastapi import Query
import pandas as pd
from chemas.movielens_feature import RatingFeatureRequest
import os

router = APIRouter(prefix="/rating_features", tags=["Rating Features"])

store_path = os.path.dirname(__file__)
fs = FeatureStore(repo_path=store_path)

@router.get("/train")
def get_train_rating(user_id: int, item_id: int):
    try:
        features = fs.get_online_features(
            features=["X_train_rating:" + f for f in [
                "timestamp_year", "timestamp_month", "timestamp_day",
                "timestamp_hour", "timestamp_dayofweek", "timestamp_is_weekend",
                "time_since_last", "rating"
            ]],
            entity_rows=[{"user_id": user_id, "item_id": item_id}]
        ).to_dict()
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test")
def get_test_rating(user_id: int, item_id: int):
    try:
        features = fs.get_online_features(
            features=["X_test_rating:" + f for f in [
                "timestamp_year", "timestamp_month", "timestamp_day",
                "timestamp_hour", "timestamp_dayofweek", "timestamp_is_weekend",
                "time_since_last", "rating"
            ]],
            entity_rows=[{"user_id": user_id, "item_id": item_id}]
        ).to_dict()
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ratings")
def add_rating_feature(
    data: RatingFeatureRequest,
    split: str = Query("train", enum=["train", "test"])  # choose X_train_rating or X_test_rating
):
    try:
        df = pd.DataFrame([{
            "user_id": data.user_id,
            "item_id": data.item_id,
            "timestamp_year": data.timestamp_year,
            "timestamp_month": data.timestamp_month,
            "timestamp_day": data.timestamp_day,
            "timestamp_hour": data.timestamp_hour,
            "timestamp_dayofweek": data.timestamp_dayofweek,
            "timestamp_is_weekend": data.timestamp_is_weekend,
            "time_since_last": data.time_since_last,
            "rating": data.rating,
            "timestamp": data.timestamp
        }])

        view_name = "X_train_rating" if split == "train" else "X_test_rating"
        fs.write_to_online_store(view_name, df)

        return {"status": "success", "message": f"Rating stored in {view_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    