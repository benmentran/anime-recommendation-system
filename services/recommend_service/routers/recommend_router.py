from fastapi import APIRouter, HTTPException

from services.recommend_service.model_loader import ModelLoader
from services.recommend_service.schemas.recommend_request import RecommendRequest, RecommendResponse

router = APIRouter(prefix="/api/v1/recommendations")
model_loader = ModelLoader()


@router.post("/user-based", response_model=RecommendResponse)
def recommend_user_based(req: RecommendRequest):
    if req.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    model = model_loader.get_user_cf_model()
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    predictions = model.predict([{"user_id": req.user_id, "item_id": i, "k": req.k} for i in range(1, 1000)])
    ranked = sorted(enumerate(predictions, 1), key=lambda x: (x[1] is not None, x[1]), reverse=True)
    return {"recommendations": [item_id for item_id, _ in ranked[:req.k]]}


@router.post("/item-based", response_model=RecommendResponse)
def recommend_item_based(req: RecommendRequest):
    if req.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    model = model_loader.get_item_cf_model()
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    predictions = model.predict([{"user_id": req.user_id, "item_id": i, "k": req.k} for i in range(1, 1000)])
    ranked = sorted(enumerate(predictions, 1), key=lambda x: (x[1] is not None, x[1]), reverse=True)
    return {"recommendations": [item_id for item_id, _ in ranked[:req.k]]}


@router.post("/content-based", response_model=RecommendResponse)
def recommend_content_based(req: RecommendRequest):
    if req.movie_id is None:
        raise HTTPException(status_code=400, detail="movie_id is required")
    model = model_loader.get_content_based_model()
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    result = model.predict([{"movie_id": req.movie_id}], params={"top_k": req.top_k})
    return {"recommendations": result[0]["recommendations"]}


@router.get("/for-you", response_model=RecommendResponse)
def recommend_for_you():
    # ponytail: hybrid CF+content wiring lands here once user vectors exist; stub keeps contract stable
    return {"recommendations": []}
