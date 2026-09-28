
from pydantic import BaseModel


class RecommendRequest(BaseModel):
    user_id: int | None = None
    item_id: int | None = None
    movie_id: int | None = None
    k: int | None = 10
    top_k: int | None = 10
    
class RecommendResponse(BaseModel):
    recommendations: list
    