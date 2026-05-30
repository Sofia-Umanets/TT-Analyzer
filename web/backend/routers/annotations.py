"""
CRUD аннотаций.
Разметки хранятся в annotations/ в том же формате что и раньше.
ID = stem видеофайла.
"""

import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from web.backend.config import ANNOTATIONS_DIR, RAW_VIDEOS_DIR, VIDEO_EXTENSIONS
from web.backend.models.schemas import AnnotationData, StrokeAnnotation, StrokeUpdate

router = APIRouter()


def _find_annotation_path(video_id: str) -> Path | None:
    """Находит файл разметки для видео по stem."""
    # 1. Прямое совпадение
    direct = ANNOTATIONS_DIR / f"{video_id}.json"
    if direct.exists():
        return direct

    # 2. Поиск по полю "video" внутри JSON
    video_filename = _find_video_filename(video_id)
    if video_filename:
        for json_file in ANNOTATIONS_DIR.glob("*.json"):
            if json_file.name.endswith("_auto.json"):
                continue
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                vid_field = data.get("video", "")
                # Совпадение по имени файла или по stem
                if vid_field == video_filename or Path(vid_field).stem == video_id:
                    return json_file
            except Exception:
                continue

    return None


def _find_video_filename(video_id: str) -> str | None:
    """Находит полное имя файла видео по stem."""
    for f in RAW_VIDEOS_DIR.iterdir():
        if f.stem == video_id and f.suffix.lower() in {e.lower() for e in VIDEO_EXTENSIONS}:
            return f.name
    return None


def _load_annotation(video_id: str) -> tuple[dict | None, Path | None]:
    """Загружает сырые данные разметки."""
    path = _find_annotation_path(video_id)
    if path is None:
        return None, None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, path


STROKE_TYPES = [
    'drive_forehand', 'topspin_forehand', 'slice_forehand',
    'drive_backhand', 'topspin_backhand', 'slice_backhand', 'other',
]

ERROR_TYPES = [
    'arm_far', 'big_swing', 'incomplete_follow_through', 'left_hand_behind_body',
    'left_hand_up', 'low_backswing', 'low_elbow_end', 'no_forearm', 'no_rotation',
    'raised_elbow', 'raised_shoulder', 'sideways_finish', 'straight_arm',
    'straight_body', 'straight_legs', 'straight_line', 'vertical_swing',
    'wrist_bent_back', 'wrist_bent_fwd', 'wrist_up',
]


@router.get("/types/list")
async def get_annotation_types():
    """Список допустимых типов ударов и кодов ошибок."""
    return {"stroke_types": STROKE_TYPES, "error_types": ERROR_TYPES}


@router.get("/{video_id}")
async def get_annotation(video_id: str):
    """Загружает разметку."""
    data, path = _load_annotation(video_id)
    if data is None:
        raise HTTPException(404, "Разметка не найдена")
    return data


@router.put("/{video_id}")
async def save_annotation(video_id: str, data: AnnotationData):
    """Полное сохранение разметки."""
    # Определяем путь: если уже есть файл — перезаписываем его
    existing_path = _find_annotation_path(video_id)
    if existing_path:
        save_path = existing_path
    else:
        save_path = ANNOTATIONS_DIR / f"{video_id}.json"

    out = data.model_dump(exclude_none=True)
    out["updated_at"] = datetime.now().isoformat()

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


@router.post("/{video_id}/strokes")
async def add_stroke(video_id: str, stroke: StrokeAnnotation):
    """Добавляет новый удар."""
    data, path = _load_annotation(video_id)

    if data is None:
        # Создаём новую разметку
        video_filename = _find_video_filename(video_id) or f"{video_id}.mp4"
        from web.backend.utils.video_converter import get_video_info
        video_path = RAW_VIDEOS_DIR / video_filename
        try:
            info = get_video_info(video_path)
        except Exception:
            info = {"fps": 30, "total_frames": 0, "duration": 0}

        data = {
            "video": video_filename,
            "fps": info.get("fps", 30),
            "frames": info.get("total_frames", 0),
            "duration": info.get("duration", 0),
            "strokes": [],
        }
        path = ANNOTATIONS_DIR / f"{video_id}.json"

    strokes = data.get("strokes", [])
    stroke_dict = stroke.model_dump(exclude_none=True)
    stroke_dict["id"] = max((s.get("id", 0) for s in strokes), default=0) + 1

    fps = data.get("fps", 30)
    if fps > 0:
        stroke_dict["start_time"] = round(stroke_dict["start_frame"] / fps, 3)
        stroke_dict["end_time"] = round(stroke_dict["end_frame"] / fps, 3)
        if stroke_dict.get("contact_frame") is not None:
            stroke_dict["contact_time"] = round(stroke_dict["contact_frame"] / fps, 3)

    strokes.append(stroke_dict)
    strokes.sort(key=lambda s: s.get("start_frame", 0))
    data["strokes"] = strokes
    data["updated_at"] = datetime.now().isoformat()

    save_path = path or ANNOTATIONS_DIR / f"{video_id}.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return stroke_dict


@router.patch("/{video_id}/strokes/{stroke_id}")
async def update_stroke(video_id: str, stroke_id: int, update: StrokeUpdate):
    """Обновляет один удар."""
    data, path = _load_annotation(video_id)
    if data is None:
        raise HTTPException(404, "Разметка не найдена")

    strokes = data.get("strokes", [])
    stroke = next((s for s in strokes if s.get("id") == stroke_id), None)
    if stroke is None:
        raise HTTPException(404, f"Удар {stroke_id} не найден")

    for key, value in update.model_dump(exclude_none=True).items():
        stroke[key] = value

    fps = data.get("fps", 30)
    if fps > 0:
        stroke["start_time"] = round(stroke["start_frame"] / fps, 3)
        stroke["end_time"] = round(stroke["end_frame"] / fps, 3)
        if stroke.get("contact_frame") is not None:
            stroke["contact_time"] = round(stroke["contact_frame"] / fps, 3)

    stroke["auto_detected"] = False
    data["updated_at"] = datetime.now().isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return stroke


@router.delete("/{video_id}/strokes/{stroke_id}")
async def delete_stroke(video_id: str, stroke_id: int):
    data, path = _load_annotation(video_id)
    if data is None:
        raise HTTPException(404, "Разметка не найдена")

    strokes = data.get("strokes", [])
    data["strokes"] = [s for s in strokes if s.get("id") != stroke_id]

    for i, s in enumerate(data["strokes"], 1):
        s["id"] = i

    data["updated_at"] = datetime.now().isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"status": "deleted"}


@router.post("/{video_id}/import-auto")
async def import_auto_annotation(video_id: str):
    auto_path = ANNOTATIONS_DIR / f"{video_id}_auto.json"
    if not auto_path.exists():
        raise HTTPException(404, "Авто-разметка не найдена")

    with open(auto_path, "r") as f:
        data = json.load(f)

    for s in data.get("strokes", []):
        s["auto_detected"] = True
    data["auto_detected"] = True
    data["updated_at"] = datetime.now().isoformat()

    save_path = ANNOTATIONS_DIR / f"{video_id}.json"
    existing = _find_annotation_path(video_id)
    if existing:
        save_path = existing

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


@router.get("/{video_id}/export")
async def export_annotation(video_id: str):
    data, _ = _load_annotation(video_id)
    if data is None:
        raise HTTPException(404, "Разметка не найдена")

    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{video_id}.json"'}
    )