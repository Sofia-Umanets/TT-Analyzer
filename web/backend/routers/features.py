"""Извлечение признаков позы из видео и управление кэшем."""

import io
import sys
import traceback
import contextlib
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

router = APIRouter()


class ExtractionStatus(str, Enum):
    idle = "idle"
    running = "running"
    done = "done"
    error = "error"


class ExtractionState(BaseModel):
    status: ExtractionStatus = ExtractionStatus.idle
    progress: float = 0
    message: str = ""
    logs: list[str] = []
    n_videos: int = 0
    n_frames: int = 0


_state = ExtractionState()


@router.post("/extract")
async def start_extraction(background_tasks: BackgroundTasks, force: bool = False):
    global _state
    if _state.status == ExtractionStatus.running:
        return _state
    _state = ExtractionState(
        status=ExtractionStatus.running,
        message="Запуск...",
        logs=["Запуск извлечения признаков..."],
    )
    background_tasks.add_task(_extract_task, force)
    return _state


@router.get("/extract/progress")
async def get_extraction_progress():
    return _state


def _extract_task(force: bool):
    try:
        from src.data.preprocessing import build_features_cache

        _state.message = "Обработка видео..."
        _state.logs.append(f"Режим: {'принудительный (force)' if force else 'инкрементальный'}")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cache = build_features_cache(force=force)

        for line in buf.getvalue().splitlines():
            line = line.strip()
            if line:
                _state.logs.append(line)

        n_videos = len(cache.get("per_video", []))
        n_frames = len(cache.get("all_features", []))

        _state.status = ExtractionStatus.done
        _state.progress = 100
        _state.message = f"Готово: {n_videos} видео, {n_frames} кадров"
        _state.n_videos = n_videos
        _state.n_frames = n_frames
        _state.logs.append(f"✓ Готово: видео={n_videos}, кадров={n_frames}")

    except Exception as e:
        _state.status = ExtractionStatus.error
        _state.message = str(e)
        _state.logs.append(f"ОШИБКА: {e}")
        traceback.print_exc()
