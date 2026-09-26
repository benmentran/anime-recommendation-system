from pydantic import BaseModel
from typing import Optional, List

class RecommendRequest(BaseModel):
    user_id: Optional[int] = None
    item_id: Optional[int] = None
    movie_id: Optional[int] = None
    k: Optional[int] = 10
    top_k: Optional[int] = 10
    
class RecommendResponse(BaseModel):
    recommendations: List
    