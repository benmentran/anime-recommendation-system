from fastapi import FastAPI

from services.recommend_service.routers import rag_router, recommend_router

app = FastAPI(title="Recommend Service")

app.include_router(recommend_router.router)
app.include_router(rag_router.router)
