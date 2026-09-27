"""CF endpoints served from local matrices (no registry, no retrain per request).

Build matrices: DATABASE_URL=... python scripts/build_cf_matrices.py
App restart picks up new matrices. Unknown user / missing model ->
popularity fallback; 503 only when nothing was ever built.
"""
from fastapi import APIRouter, HTTPException

from services.recommend_service.model_loader import ModelLoader
from services.recommend_service.schemas.recommend_request import RecommendRequest, RecommendResponse

router = APIRouter(prefix="/api/v1/recommendations")
model_loader = ModelLoader()


def _ids(ranked, k: int) -> list:
    """(item, score) pairs -> clean item ids (drop NaN/None scores)."""
    out = []
    for item, score in ranked:
        try:
            bad = score is None or score != score
        except Exception:
            bad = True
        if not bad:
            out.append(item)
        if len(out) >= k:
            break
    return out


def _popular_or_503(k: int) -> list:
    model_loader.ensure_loaded()
    pop = model_loader.get_popular(k)
    if not pop:
        raise HTTPException(status_code=503, detail="model not loaded")
    return pop


@router.post("/user-based", response_model=RecommendResponse)
def recommend_user_based(req: RecommendRequest):
    if req.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    model_loader.ensure_loaded()
    model = model_loader.get_user_cf_model()
    if model is None:
        return {"recommendations": _popular_or_503(req.k or 10)}
    return {"recommendations": _ids(model.recommend(req.user_id, req.k or 10), req.k or 10)
            or _popular_or_503(req.k or 10)}


@router.post("/item-based", response_model=RecommendResponse)
def recommend_item_based(req: RecommendRequest):
    if req.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    model_loader.ensure_loaded()
    model = model_loader.get_item_cf_model()
    if model is None:
        return {"recommendations": _popular_or_503(req.k or 10)}
    return {"recommendations": _ids(model.recommend(req.user_id, req.k or 10), req.k or 10)
            or _popular_or_503(req.k or 10)}


@router.post("/content-based", response_model=RecommendResponse)
def recommend_content_based(req: RecommendRequest):
    if req.movie_id is None:
        raise HTTPException(status_code=400, detail="movie_id is required")
    model_loader.ensure_loaded()
    model = model_loader.get_content_based_model()
    if model is None:
        return {"recommendations": _popular_or_503(req.top_k or 10)}
    recs = model.recommend(req.movie_id, top_k=req.top_k or 10)
    return {"recommendations": list(recs) or _popular_or_503(req.top_k or 10)}


@router.get("/for-you", response_model=RecommendResponse)
def recommend_for_you(user_id: int | None = None, k: int = 10):
    """Hybrid: interleave user-based + item-based, content from top item, popularity fill."""
    model_loader.ensure_loaded()
    if user_id is None:
        return {"recommendations": _popular_or_503(k)}
    seen, out = set(), []
    for model, fn in ((model_loader.get_user_cf_model(), "user"),
                      (model_loader.get_item_cf_model(), "item")):
        if model is None:
            continue
        try:
            recs = model.recommend(user_id, k) or []
        except Exception:
            continue
        for item, _ in recs:
            if item not in seen:
                seen.add(item)
                out.append(item)
    content = model_loader.get_content_based_model()
    if content is not None and out:
        try:
            for mid in content.recommend(out[0], top_k=k) or []:
                if mid not in seen:
                    seen.add(mid)
                    out.append(mid)
        except Exception:
            pass
    for pid in model_loader.get_popular(k):
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    if not out:
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"recommendations": out[:k]}
