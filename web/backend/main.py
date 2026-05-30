"""
Точка входа FastAPI.
Запуск: uvicorn web.backend.main:app --reload --port 8000
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.backend.config import (
    CORS_ORIGINS, RAW_VIDEOS_DIR, THUMBNAILS_DIR, OUTPUTS_DIR
)
from web.backend.routers import videos, annotations, analysis, visualization, training, features, compare
from web.backend.services.ml_bridge import MLBridge

ml_bridge = MLBridge()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_bridge.load_models()
    app.state.ml = ml_bridge
    yield
    ml_bridge.cleanup()


app = FastAPI(
    title="Table Tennis Analyzer",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Все видео лежат в raw_videos/
app.mount("/media/videos", StaticFiles(directory=str(RAW_VIDEOS_DIR)), name="videos")
app.mount("/media/thumbnails", StaticFiles(directory=str(THUMBNAILS_DIR)), name="thumbnails")
app.mount("/media/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["annotations"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(visualization.router, prefix="/api/viz", tags=["visualization"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(features.router, prefix="/api/features", tags=["features"])
app.include_router(compare.router, prefix="/api/compare", tags=["compare"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": ml_bridge.is_loaded(),
        "models_available": ml_bridge.available_models(),
    }