import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.recommend_service.routers.recommend_router import (
    router as recommend_router,
)
from services.web_service.routes import (
    anime_router,
    auth_router,
    list_router,
    rag_proxy_router,
)

app = FastAPI(title="Anime BFF")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(anime_router.router)
app.include_router(list_router.router)
app.include_router(rag_proxy_router.router)  # BFF proxy -> recommend_service /api/v1/rag/ask
app.include_router(recommend_router)  # source of truth for /api/v1/recommendations/*


@app.get("/health")
async def health():
    return {"ok": True}
