BASE_PATH = "feature_repo"

_stores = {}


def _fs(name):
    from feast import FeatureStore  # lazy: importable without feast installed

    if name not in _stores:
        _stores[name] = FeatureStore(repo_path=f"{BASE_PATH}/{name}")
    return _stores[name]

def get_user_features_online(user_ids):
    entity_rows = [{"user_id": uid} for uid in user_ids]
    user_df = _fs("store_1000").get_online_features(
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
        ],
        entity_rows=entity_rows
    ).to_df()

    return user_df

def get_movie_features_online(movie_ids):
    entity_rows = [{"movie_id": mid} for mid in movie_ids]
    movie_df = _fs("store_1000").get_online_features(
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
        ],
        entity_rows=entity_rows
    ).to_df()

    return movie_df

def get_rating_features_online(user_ids, item_ids):
    entity_rows = [{"user_id": u, "item_id": m} for u, m in zip(user_ids, item_ids)]
    rating_df = _fs("store_1000").get_online_features(
        features=[
            "X_train_rating:timestamp_year",
            "X_train_rating:timestamp_month",
            "X_train_rating:timestamp_day",
            "X_train_rating:timestamp_hour",
            "X_train_rating:timestamp_dayofweek",
            "X_train_rating:timestamp_is_weekend",
            "X_train_rating:time_since_last",
            "X_train_rating:rating"
        ],
        entity_rows=entity_rows
    ).to_df()

    return rating_df
