from feast import Entity, FeatureView, Field, FileSource, FeatureStore
from feast import ValueType
from feast.types import Int64, Float64, String
import os


user_source = FileSource(
    path=os.path.join(os.path.dirname(__file__).pảent[2], 'data/feature/users_movielens/user_features.parquet'), 
    event_timestamp_column="event_timestamp")

user = Entity(name='user_id', 
              join_keys=['user_id'], 
              value_type=ValueType.INT64)

user_fv = FeatureView(
    name="user_features",
    entities=[user],
    ttl=None,
    schema=[
        Field(name='age', dtype=Int64),
        Field(name='zip_code', dtype=String),
        Field(name='gender_F', dtype=Float64),
        Field(name='gender_M', dtype=Float64),
        Field(name='occupation_administrator', dtype=Float64),
        Field(name='occupation_artist', dtype=Float64),
        Field(name='occupation_doctor', dtype=Float64),
        Field(name='occupation_educator', dtype=Float64),
        Field(name='occupation_engineer', dtype=Float64),
        Field(name='occupation_entertainment', dtype=Float64),
        Field(name='occupation_executive', dtype=Float64),
        Field(name='occupation_healthcare', dtype=Float64),
        Field(name='occupation_homemaker', dtype=Float64),
        Field(name='occupation_lawyer', dtype=Float64),
        Field(name='occupation_librarian', dtype=Float64),
        Field(name='occupation_marketing', dtype=Float64),
        Field(name='occupation_none', dtype=Float64),
        Field(name='occupation_other', dtype=Float64),
        Field(name='occupation_programmer', dtype=Float64),
        Field(name='occupation_retired', dtype=Float64),
        Field(name='occupation_salesman', dtype=Float64),
        Field(name='occupation_scientist', dtype=Float64),
        Field(name='occupation_student', dtype=Float64),
        Field(name='occupation_technician', dtype=Float64),
        Field(name='occupation_writer', dtype=Float64),
    ],
    source=user_source
)

store_path = os.path.dirname(__file__)
fs = FeatureStore(repo_path=store_path)
fs.apply([user, user_fv])