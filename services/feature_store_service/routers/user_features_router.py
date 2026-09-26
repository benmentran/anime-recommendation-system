from fastapi import APIRouter, HTTPException
from feast import FeatureStore
import pandas as pd
from schemas.movielens_feature import UserFeatureRequest
import os

router = APIRouter(prefix="/user_features", tags=["User Features"])

store_path = os.path.dirname(__file__)
fs = FeatureStore(repo_path=store_path)

@router.get("/{user_id}")
def get_user_features(user_id: int):
    try:
        features = fs.get_online_features(
            features=["user_features:" + f for f in [
                "age", "zip_code", "gender_F", "gender_M",
                "occupation_administrator", "occupation_artist", "occupation_doctor",
                "occupation_educator", "occupation_engineer", "occupation_entertainment",
                "occupation_executive", "occupation_healthcare", "occupation_homemaker",
                "occupation_lawyer", "occupation_librarian", "occupation_marketing",
                "occupation_none", "occupation_other", "occupation_programmer",
                "occupation_retired", "occupation_salesman", "occupation_scientist",
                "occupation_student", "occupation_technician", "occupation_writer"
            ]],
            entity_rows=[{"user_id": user_id}]
        ).to_dict()
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
def add_user_features(data: UserFeatureRequest):
    try:
        df = pd.DataFrame([data.dict()])
        fs.write_to_online_store("user_features", df)
        return {"status": "success", "message": f"user {data.user_id} stored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    