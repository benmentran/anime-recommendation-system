from feast import Entity, FeatureView, Field, FileSource, FeatureStore
from feast import ValueType
from feast.types import Float64, Int32, Int64, Array, Float32
import os

    
movie_source = FileSource(
    path=os.path.join(os.path.dirname(__file__).parent[2], "data/feature/movies_movielens/movie_features.parquet"),
    event_timestamp_column='release_date')

movie = Entity(name='movie_id', 
              join_keys=['movie_id'], 
              value_type=ValueType.INT64)

movie_fv = FeatureView(
    name="movie_features_movielens",
    entities=[movie],
    ttl=None,
    schema=[
        Field(name='unknown', dtype=Int64),
        Field(name='Action', dtype=Int64),
        Field(name='Adventure', dtype=Int64),
        Field(name='Animation', dtype=Int64),
        Field(name="Childrens", dtype=Int64),
        Field(name='Comedy', dtype=Int64),
        Field(name='Crime', dtype=Int64),
        Field(name='Documentary', dtype=Int64),
        Field(name='Drama', dtype=Int64),
        Field(name='Fantasy', dtype=Int64),
        Field(name='Film_Noir', dtype=Int64),
        Field(name='Horror', dtype=Int64),
        Field(name='Musical', dtype=Int64),
        Field(name='Mystery', dtype=Int64),
        Field(name='Romance', dtype=Int64),
        Field(name='Sci_Fi', dtype=Int64),
        Field(name='Thriller', dtype=Int64),
        Field(name='War', dtype=Int64),
        Field(name='Western', dtype=Int64),
        Field(name='release_date_year', dtype=Float64),
        Field(name='release_date_month', dtype=Float64),
        Field(name='release_date_day', dtype=Float64),
        Field(name='release_date_hour', dtype=Float64),
        Field(name='release_date_dayofweek', dtype=Float64),
        Field(name='release_date_is_weekend', dtype=Int32),
        Field(name='title_tfidf', dtype=Array(Float32), vector_index=True, vector_search_metric="COSINE"),
    ],
    online=True,
    source=movie_source,
)

os.makedirs("store_1000", exist_ok=True)
store_path = os.path.join(os.path.dirname(__file__), "store_1000")
fs_1000 = FeatureStore(repo_path=store_path)
fs_1000.apply([movie, movie_fv])
