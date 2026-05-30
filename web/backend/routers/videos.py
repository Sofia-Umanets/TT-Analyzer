"""
Список видео, загрузка, удаление.
Все видео хранятся в одной папке: raw_videos/
Разметки — в annotations/
ID видео = stem (имя без расширения).
"""

import uuid
import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from web.backend.config import (
    UPLOAD_DIR, RAW_VIDEOS_DIR, THUMBNAILS_DIR,
    ANNOTATIONS_DIR, MAX_UPLOAD_SIZE_MB, ANALYSIS_CACHE_DIR,
    VIDEO_EXTENSIONS,
)
from web.backend.models.schemas import VideoInfo, VideoListResponse, VideoStatus, AnnotationStatus
from web.backend.utils.video_converter import convert_video, get_video_info, generate_thumbnail, is_mp4_h264

router = APIRouter()

# Кэш метаданных видео (чтобы не вызывать ffprobe каждый раз)
_INFO_CACHE_FILE = THUMBNAILS_DIR / "_video_info_cache.json"

# Статус фоновой конвертации: stem -> "converting" | "done" | "error:<msg>"
_converting: dict[str, str] = {}


def _load_info_cache() -> dict:
    if _INFO_CACHE_FILE.exists():
        try:
            with open(_INFO_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_info_cache(cache: dict):
    with open(_INFO_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _get_cached_info(video_path: Path) -> dict:
    """Получает метаданные видео с кэшированием."""
    cache = _load_info_cache()
    key = video_path.name
    mtime = video_path.stat().st_mtime

    if key in cache and cache[key].get("_mtime") == mtime:
        return cache[key]

    try:
        info = get_video_info(video_path)
    except Exception as e:
        print(f"  [WARN] Не удалось получить инфо {video_path.name}: {e}")
        info = {"fps": 30, "total_frames": 0, "width": 0, "height": 0, "duration": 0}

    info["_mtime"] = mtime
    info["size_mb"] = round(video_path.stat().st_size / 1024 / 1024, 2)
    cache[key] = info
    _save_info_cache(cache)
    return info


def _find_annotation(video_stem: str, video_filename: str) -> tuple[AnnotationStatus, Path | None]:
    """
    Ищет разметку для видео.
    Стратегия:
      1. annotations/{stem}.json
      2. Если не найден — ищем JSON где "video" == video_filename
      3. annotations/{stem}_auto.json
    """
    # Прямое совпадение по stem
    direct = ANNOTATIONS_DIR / f"{video_stem}.json"
    if direct.exists():
        try:
            with open(direct, "r") as f:
                data = json.load(f)
            is_auto = data.get("auto_detected", False)
            if is_auto:
                strokes = data.get("strokes", [])
                all_auto = all(s.get("auto_detected", False) for s in strokes)
                return (AnnotationStatus.auto if all_auto else AnnotationStatus.manual), direct
            return AnnotationStatus.manual, direct
        except Exception:
            return AnnotationStatus.manual, direct

    # Поиск по полю "video" внутри JSON
    for json_file in ANNOTATIONS_DIR.glob("*.json"):
        if json_file.name.endswith("_auto.json"):
            continue
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            if data.get("video") == video_filename:
                return AnnotationStatus.manual, json_file
        except Exception:
            continue

    # Авто-разметка
    auto = ANNOTATIONS_DIR / f"{video_stem}_auto.json"
    if auto.exists():
        return AnnotationStatus.auto, auto

    return AnnotationStatus.none, None


def _build_video_info(video_path: Path) -> VideoInfo:
    """Собирает полную информацию о видео."""
    stem = video_path.stem
    info = _get_cached_info(video_path)

    # Превью
    thumb_path = THUMBNAILS_DIR / f"{stem}.jpg"
    if not thumb_path.exists():
        try:
            generate_thumbnail(video_path, thumb_path)
        except Exception:
            pass
    thumb_url = f"/media/thumbnails/{quote(stem)}.jpg" if thumb_path.exists() else None

    # Разметка
    ann_status, ann_path = _find_annotation(stem, video_path.name)

    # Анализ
    has_analysis = (ANALYSIS_CACHE_DIR / f"{stem}.json").exists()

    # URL для воспроизведения — через /media/videos/ (= raw_videos/)
    video_url = f"/media/videos/{quote(video_path.name)}"

    return VideoInfo(
        id=stem,
        filename=video_path.name,
        status=VideoStatus.ready,
        fps=info.get("fps", 0),
        total_frames=info.get("total_frames", 0),
        duration=info.get("duration", 0),
        width=info.get("width", 0),
        height=info.get("height", 0),
        size_mb=info.get("size_mb", 0),
        thumbnail=thumb_url,
        annotation_status=ann_status,
        has_analysis=has_analysis,
        video_url=video_url,
    )


@router.get("", response_model=VideoListResponse)
async def list_videos():
    """Список всех видео из raw_videos/."""
    videos = []
    for f in sorted(RAW_VIDEOS_DIR.iterdir()):
        if f.suffix.lower() in {e.lower() for e in VIDEO_EXTENSIONS} and not f.name.startswith('.'):
            try:
                videos.append(_build_video_info(f))
            except Exception as e:
                print(f"[WARN] Пропускаем {f.name}: {e}")
    return VideoListResponse(videos=videos, total=len(videos))


@router.get("/{video_id}/status")
async def get_video_conversion_status(video_id: str):
    """Статус конвертации видео: converting | ready | error."""
    status = _converting.get(video_id)
    if status == "converting":
        return {"status": "converting"}
    if status == "done":
        return {"status": "ready"}
    if status and status.startswith("error:"):
        raise HTTPException(500, status[6:])
    # Нет записи — видео уже существовало до запуска сервера
    for f in RAW_VIDEOS_DIR.iterdir():
        if f.stem == video_id:
            return {"status": "ready"}
    raise HTTPException(404, f"Видео не найдено: {video_id}")


@router.get("/{video_id}/web_url")
async def get_web_url(video_id: str):
    """
    URL для воспроизведения + метаданные (fps, total_frames, duration).
    Возвращает 202 если конвертация ещё идёт.
    """
    status = _converting.get(video_id)
    if status == "converting":
        raise HTTPException(202, "Видео ещё конвертируется")

    for f in RAW_VIDEOS_DIR.iterdir():
        if f.stem == video_id and f.suffix.lower() in {e.lower() for e in VIDEO_EXTENSIONS}:
            info = _get_cached_info(f)
            return {
                "url": f"/media/videos/{quote(f.name)}",
                "fps": info.get("fps", 30),
                "total_frames": info.get("total_frames", 0),
                "duration": info.get("duration", 0),
            }
    raise HTTPException(404, f"Видео не найдено: {video_id}")


@router.get("/{video_id}")
async def get_video(video_id: str):
    """Получить информацию о видео по ID (stem)."""
    for f in RAW_VIDEOS_DIR.iterdir():
        if f.stem == video_id and f.suffix.lower() in {e.lower() for e in VIDEO_EXTENSIONS}:
            return _build_video_info(f)
    raise HTTPException(404, f"Видео не найдено: {video_id}")


@router.post("", response_model=VideoInfo)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Загрузка нового видео.
    Конвертируется в MP4 и сохраняется в raw_videos/.
    """
    if file.size and file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"Файл слишком большой (макс. {MAX_UPLOAD_SIZE_MB}МБ)")

    original_name = file.filename or "video.mp4"
    suffix = Path(original_name).suffix or ".mp4"

    # Генерируем уникальное имя если такое уже есть
    base_stem = Path(original_name).stem
    target_stem = base_stem
    counter = 1
    while (RAW_VIDEOS_DIR / f"{target_stem}.mp4").exists():
        target_stem = f"{base_stem}_{counter}"
        counter += 1

    upload_path = UPLOAD_DIR / f"{target_stem}{suffix}"

    with open(upload_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    print(f"[Upload] {upload_path.name} ({upload_path.stat().st_size / 1024 / 1024:.1f} МБ)")

    # Если уже MP4 с правильным кодеком — можно просто скопировать
    # Но для надёжности всегда конвертируем
    background_tasks.add_task(_process_upload, target_stem, upload_path)

    return VideoInfo(
        id=target_stem,
        filename=f"{target_stem}.mp4",
        status=VideoStatus.converting,
        video_url="",
    )


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Удаляет видео и связанные файлы."""
    found = False
    for f in RAW_VIDEOS_DIR.iterdir():
        if f.stem == video_id:
            f.unlink()
            found = True
            break

    if not found:
        raise HTTPException(404, "Видео не найдено")

    # Удаляем превью и кэш анализа
    (THUMBNAILS_DIR / f"{video_id}.jpg").unlink(missing_ok=True)
    (ANALYSIS_CACHE_DIR / f"{video_id}.json").unlink(missing_ok=True)

    # НЕ удаляем разметку — она может быть ценной
    return {"status": "deleted"}


def _process_upload(target_stem: str, upload_path: Path):
    """Фоновая конвертация загруженного видео в MP4."""
    _converting[target_stem] = "converting"
    try:
        output_path = RAW_VIDEOS_DIR / f"{target_stem}.mp4"

        # Новое видео (без существующей разметки) конвертируем с -g 1:
        # каждый кадр становится ключевым → мгновенный seek в браузере.
        # Старые видео с разметкой трогать нельзя — кадровые метки S/C/E съедут.
        has_annotation = (
            (ANNOTATIONS_DIR / f"{target_stem}.json").exists() or
            (ANNOTATIONS_DIR / f"{target_stem}_auto.json").exists()
        )
        make_keyframes = not has_annotation
        if make_keyframes:
            print(f"[Upload] {target_stem}: новое видео, конвертируем с all-keyframes (-g 1)")
        else:
            print(f"[Upload] {target_stem}: есть разметка, конвертируем без изменения структуры кадров")

        # MP4 с H.264 без разметки всё равно перекодируем, чтобы добавить -g 1.
        # С разметкой — копируем как раньше, чтобы не трогать FPS/кадры.
        if is_mp4_h264(upload_path) and not make_keyframes:
            print(f"[Upload] {target_stem}: уже H.264 MP4, копируем без перекодирования")
            import shutil as _shutil
            _shutil.copy2(upload_path, output_path)
        else:
            convert_video(upload_path, output_path, make_keyframes=make_keyframes)

        if not output_path.exists():
            raise RuntimeError(f"Файл не создан: {output_path}")

        info = get_video_info(output_path)
        print(f"[OK] {target_stem}: {info['total_frames']} кадров, {info['fps']} fps")

        generate_thumbnail(output_path, THUMBNAILS_DIR / f"{target_stem}.jpg")
        _converting[target_stem] = "done"

    except Exception as e:
        print(f"[ОШИБКА] Конвертация {target_stem}: {e}")
        import traceback
        traceback.print_exc()
        _converting[target_stem] = f"error:{e}"
    finally:
        upload_path.unlink(missing_ok=True)