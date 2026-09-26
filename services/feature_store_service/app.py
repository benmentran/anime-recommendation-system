from fastapi import FastAPI

try:  # repo root / pytest / Airflow layout
    from services.feature_store_service.routers import (
        features_router,
        movie_features_router,
        rating_features_router,
        user_features_router,
    )
except ImportError:  # container layout (service dir is WORKDIR)
    from routers import (
        features_router,
        movie_features_router,
        rating_features_router,
        user_features_router,
    )

app = FastAPI(title="Feature Store Service")

# Include routers
app.include_router(features_router.router)  # merged retrieval: /features/online|historical/*
app.include_router(movie_features_router.router)
app.include_router(rating_features_router.router)
app.include_router(user_features_router.router)
