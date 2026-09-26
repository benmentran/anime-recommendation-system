import pandas as pd

REPO_PATH = "feature_repo"

_store = None


def _fs():
    global _store
    if _store is None:
        from feast import FeatureStore  # lazy: importable without feast installed

        _store = FeatureStore(repo_path=REPO_PATH)
    return _store

def get_user_features_df():
    entity_df = pd.read_parquet("feature_repo/data/users_movielens/user_features.parquet")
    entity_df["event_timestamp"] = pd.to_datetime(entity_df["event_timestamp"])

    user_df = _fs().get_historical_features(
        entity_df=entity_df,
        features=[
            "user_features:age", 
            "user_features:zip_code",
            "user_features:gender_F",
            "user_features:gender_M",
            "user_features:occupation_administrator",
            "user_features:occupation_artist",
            "user_features:occupation_doctor",
            "user_features:occupation_educator",
            "user_features:occupation_engineer",
            "user_features:occupation_entertainment",
            "user_features:occupation_executive",
            "user_features:occupation_healthcare ",
            "user_features:occupation_homemaker",
            "user_features:occupation_lawyer",
            "user_features:occupation_librarian",
            "user_features:occupation_marketing",
            "user_features:occupation_none",
            "user_features:occupation_other",
            "user_features:occupation_programmer",
            "user_features:occupation_retired",
            "user_features:occupation_salesman",
            "user_features:occupation_scientist",
            "user_features:occupation_student",
            "user_features:occupation_technician",
            "user_features:occupation_writer",
        ]
    ).to_df()
    
    return user_df

def get_movie_features_df():
    entity_df = pd.read_parquet("feature_repo/data/movies_movielens/movie_features_train.parquet")
    entity_df["release_date"] = pd.to_datetime(entity_df["release_date"])
    entity_df = entity_df.rename(columns={"release_date": "event_timestamp"})

    movie_df = _fs().get_historical_features(
        entity_df=entity_df,
        features=[
            "movie_features:unknown",
            "movie_features:Action",
            "movie_features:Adventure",
            "movie_features:Animation",
            "movie_features:Children",
            "movie_features:Comedy",
            "movie_features:Crime",
            "movie_features:Documentary",
            "movie_features:Drama",
            "movie_features:Fantasy",
            "movie_features:Film_Noir",
            "movie_features:Horror",
            "movie_features:Musical",
            "movie_features:Mystery",
            "movie_features:Romance",
            "movie_features:Sci_Fi",
            "movie_features:Thriller",
            "movie_features:War",
            "movie_features:Western",
            "movie_features:release_date_year",
            "movie_features:release_date_month",
            "movie_features:release_date_day",
            "movie_features:release_date_hour",
            "movie_features:release_date_daypofweek",
            "movie_features:release_date_is_weekend",
            "movie_features:title_tfidf",
        ]
    ).to_df()
    
    return movie_df

def get_rating_features_df():
    entity_df = pd.read_parquet("feature_repo/data/ratings_movielens/rating_train.parquet")
    entity_df["timestamp"] = pd.to_datetime(entity_df["timestamp"])
    entity_df = entity_df.rename(columns={"timestamp": "event_timestamp"})

    rating_df = _fs().get_historical_features(
        entity_df=entity_df,
        features=[
            "X_train_rating:timestamp_year",
            "X_train_rating:timestamp_month",
            "X_train_rating:timestamp_day",
            "X_train_rating:timestamp_hour",
            "X_train_rating:timestamp_dayofweek",
            "X_train_rating:timestamp_is_weekend",
            "X_train_rating:time_since_last",
            "X_train_rating:rating"
        ]
    ).to_df()
    
    return rating_df
