"""Сервис работы с видео-файлами."""

import json
from pathlib import Path
from web.backend.config import RAW_VIDEOS_DIR

VIDEOS_DB = RAW_VIDEOS_DIR / "_videos_index.json"


class VideoService:
    @staticmethod
    def get_video_path(video_id: str) -> Path:
        return RAW_VIDEOS_DIR / f"{video_id}.mp4"

    @staticmethod
    def exists(video_id: str) -> bool:
        return (RAW_VIDEOS_DIR / f"{video_id}.mp4").exists()

    @staticmethod
    def load_db() -> dict:
        if VIDEOS_DB.exists():
            with open(VIDEOS_DB, "r") as f:
                return json.load(f)
        return {}