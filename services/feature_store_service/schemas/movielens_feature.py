from pydantic import BaseModel
from typing import List
from datetime import datetime

class MovieLensFeatureRequest(BaseModel):
    movie_id: int
    unknown: int
    Action: int
    Adventure: int
    Animation: int
    Childrens: int
    Comedy: int
    Crime: int
    Documentary: int
    Drama: int
    Fantasy: int
    Film_Noir: int
    Horror: int
    Musical: int
    Mystery: int
    Romance: int
    Sci_Fi: int
    Thriller: int
    War: int
    Western: int
    release_date_year: float
    release_date_month: float
    release_date_day: float
    release_date_hour: float
    release_date_dayofweek: float
    release_date_is_weekend: int
    title_tfidf: List[float]
    release_date: datetime   # event_timestamp

class RatingFeatureRequest(BaseModel):
    user_id: int
    item_id: int
    timestamp_year: int
    timestamp_month: int
    timestamp_day: int
    timestamp_hour: int
    timestamp_dayofweek: int
    timestamp_is_weekend: int
    time_since_last: float
    rating: int
    timestamp: datetime   # event_timestamp

class UserFeatureRequest(BaseModel):
    user_id: int
    age: int
    zip_code: str
    gender_F: int
    gender_M: int
    occupation_administrator: int
    occupation_artist: int
    occupation_doctor: int
    occupation_educator: int
    occupation_engineer: int
    occupation_entertainment: int
    occupation_executive: int
    occupation_healthcare: int
    occupation_homemaker: int
    occupation_lawyer: int
    occupation_librarian: int
    occupation_marketing: int
    occupation_none: int
    occupation_other: int
    occupation_programmer: int
    occupation_retired: int
    occupation_salesman: int
    occupation_scientist: int
    occupation_student: int
    occupation_technician: int
    occupation_writer: int
    event_timestamp: datetime
    