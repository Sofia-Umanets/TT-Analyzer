"""Запуск ML-анализа, получение результатов."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks

from web.backend.config import RAW_VIDEOS_DIR, ANALYSIS_CACHE_DIR, VIDEO_EXTENSIONS
from web.backend.models.schemas import AnalysisProgress, AnalysisStatus

router = APIRouter()
_progress: dict[str, AnalysisProgress] = {}


def _find_video_path(video_id: str) -> Path | None:
    for f in RAW_VIDEOS_DIR.iterdir():
        if f.stem == video_id and f.suffix.lower() in {e.lower() for e in VIDEO_EXTENSIONS}:
            return f
    return None


@router.post("/{video_id}/run")
async def run_analysis(video_id: str, request: Request, background_tasks: BackgroundTasks):
    video_path = _find_video_path(video_id)
    if video_path is None:
        raise HTTPException(404, "Видео не найдено")

    if video_id in _progress and _progress[video_id].status not in (
        AnalysisStatus.done, AnalysisStatus.error, AnalysisStatus.idle
    ):
        return _progress[video_id]

    ml = request.app.state.ml
    _progress[video_id] = AnalysisProgress(
        video_id=video_id, status=AnalysisStatus.extracting_features,
        progress=0, message="Запуск...",
    )
    background_tasks.add_task(_run_task, video_id, video_path, ml)
    return _progress[video_id]


@router.get("/{video_id}/progress")
async def get_progress(video_id: str):
    if video_id not in _progress:
        if (ANALYSIS_CACHE_DIR / f"{video_id}.json").exists():
            return AnalysisProgress(video_id=video_id, status=AnalysisStatus.done, progress=100, message="Готово")
        return AnalysisProgress(video_id=video_id, status=AnalysisStatus.idle, progress=0, message="Не запущен")
    return _progress[video_id]


@router.get("/{video_id}/result")
async def get_result(video_id: str):
    path = ANALYSIS_CACHE_DIR / f"{video_id}.json"
    if not path.exists():
        raise HTTPException(404, "Анализ не найден")
    with open(path, "r") as f:
        return json.load(f)


@router.get("/{video_id}/phases")
async def get_phases(video_id: str):
    path = ANALYSIS_CACHE_DIR / f"{video_id}.json"
    if not path.exists():
        raise HTTPException(404, "Анализ не найден")
    with open(path, "r") as f:
        data = json.load(f)
    return {"phases": data["phases"], "fps": data["fps"], "total_frames": data["total_frames"]}


def _run_task(video_id: str, video_path: Path, ml):
    try:
        def update(status, progress, message):
            _progress[video_id] = AnalysisProgress(
                video_id=video_id, status=status, progress=progress, message=message)

        result = ml.full_analysis(video_path, progress_callback=update)
        result["video_id"] = video_id

        with open(ANALYSIS_CACHE_DIR / f"{video_id}.json", "w") as f:
            json.dump(result, f, ensure_ascii=False)

        ml.save_auto_annotation(video_id, result)
        update(AnalysisStatus.done, 100, "Готово")
    except Exception as e:
        _progress[video_id] = AnalysisProgress(
            video_id=video_id, status=AnalysisStatus.error, progress=0, message=str(e))
        import traceback
        traceback.print_exc()