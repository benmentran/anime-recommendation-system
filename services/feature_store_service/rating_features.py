from feast import Entity, FeatureView, Field, FileSource, FeatureStore
from feast import ValueType
from feast.types import Float64, Int32, Int64
import os


X_train_source = FileSource(
    path=os.path.join(os.path.dirname(__file__).parent[2], 'data/feature/ratings_movielens/rating_train.parquet'),
    event_timestamp_column="timestamp")

user = Entity(name='user_id', 
              join_keys=['user_id'], 
              value_type=ValueType.INT64)

item = Entity(name='item_id',
              join_keys=['item_id'],
              value_type=ValueType.INT64)

X_train_fv = FeatureView(
    name="X_train_rating",
    entities=[user, item],
    ttl=None,
    schema=[
        Field(name='timestamp_year', dtype=Int32),
        Field(name='timestamp_month', dtype=Int32),
        Field(name='timestamp_day', dtype=Int32),
        Field(name='timestamp_hour', dtype=Int32),
        Field(name='timestamp_dayofweek', dtype=Int32),
        Field(name="timestamp_is_weekend", dtype=Int32),
        Field(name="time_since_last", dtype=Float64),
        Field(name='rating', dtype=Int64),
    ],
    source=X_train_source
)

X_test_source = FileSource(
    path=os.path.join(os.path.dirname(__file__).parent[2], "data/feature/ratings_movielens/rating_test.parquet"),
    event_timestamp_column="timestamp")

X_test_fv = FeatureView(
    name="X_test_rating",
    entities=[user, item],
    ttl=None,
    schema=[
        Field(name='timestamp_year', dtype=Int32),
        Field(name='timestamp_month', dtype=Int32),
        Field(name='timestamp_day', dtype=Int32),
        Field(name='timestamp_hour', dtype=Int32),
        Field(name='timestamp_dayofweek', dtype=Int32),
        Field(name="timestamp_is_weekend", dtype=Int32),
        Field(name="time_since_last", dtype=Float64),
        Field(name='rating', dtype=Int64),
    ],
    source=X_test_source
)

store_path = os.path.dirname(__file__)
fs = FeatureStore(repo_path=store_path)
fs.apply([user, item, X_train_fv, X_test_fv])