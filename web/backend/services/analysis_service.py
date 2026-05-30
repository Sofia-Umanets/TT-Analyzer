"""Сервис анализа."""

import json
from pathlib import Path
from web.backend.config import ANALYSIS_CACHE_DIR


class AnalysisService:
    @staticmethod
    def result_exists(video_id: str) -> bool:
        return (ANALYSIS_CACHE_DIR / f"{video_id}.json").exists()

    @staticmethod
    def load_result(video_id: str) -> dict | None:
        path = ANALYSIS_CACHE_DIR / f"{video_id}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)