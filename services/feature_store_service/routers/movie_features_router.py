from fastapi import APIRouter, HTTPException
from feast import FeatureStore
import pandas as pd
from chemas.movielens_feature import MovieLensFeatureRequest
import os

router = APIRouter(prefix="/movie_features_movielens", tags=["Movie Features Movielens"])

store_path_1000 = os.path.join(os.path.dirname(__file__), "..", "store_1000")
fs_1000 = FeatureStore(repo_path=store_path_1000)

@router.get("/{movie_id}")
def get_movie_features_movielens(movie_id: int):
    try:
        features = fs_1000.get_online_features(
            features=["movie_features_movielens:" + f for f in [
                "unknown", "Action", "Adventure", "Animation", "Childrens",
                "Comedy", "Crime", "Documentary", "Drama", "Fantasy",
                "Film_Noir", "Horror", "Musical", "Mystery", "Romance",
                "Sci_Fi", "Thriller", "War", "Western",
                "release_date_year", "release_date_month", "release_date_day",
                "release_date_hour", "release_date_dayofweek", "release_date_is_weekend",
                "title_tfidf"
            ]],
            entity_rows=[{"movie_id": movie_id}]
        ).to_dict()
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/features/movielens/movie")
def add_movielens_movie_feature(data: MovieLensFeatureRequest):
    try:
        df = pd.DataFrame([{
            "movie_id": data.movie_id,
            "unknown": data.unknown,
            "Action": data.Action,
            "Adventure": data.Adventure,
            "Animation": data.Animation,
            "Childrens": data.Childrens,
            "Comedy": data.Comedy,
            "Crime": data.Crime,
            "Documentary": data.Documentary,
            "Drama": data.Drama,
            "Fantasy": data.Fantasy,
            "Film_Noir": data.Film_Noir,
            "Horror": data.Horror,
            "Musical": data.Musical,
            "Mystery": data.Mystery,
            "Romance": data.Romance,
            "Sci_Fi": data.Sci_Fi,
            "Thriller": data.Thriller,
            "War": data.War,
            "Western": data.Western,
            "release_date_year": data.release_date_year,
            "release_date_month": data.release_date_month,
            "release_date_day": data.release_date_day,
            "release_date_hour": data.release_date_hour,
            "release_date_dayofweek": data.release_date_dayofweek,
            "release_date_is_weekend": data.release_date_is_weekend,
            "title_tfidf": data.title_tfidf,
            "release_date": data.release_date  # event_timestamp
        }])

        fs_1000.write_to_online_store("movie_features_movielens", df)

        return {"status": "success", "message": f"Movie {data.movie_id} feature stored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
