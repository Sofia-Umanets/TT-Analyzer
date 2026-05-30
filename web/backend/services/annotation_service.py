"""
Сервис работы с аннотациями.
Ищет разметку по stem (имя без расширения) в папке annotations/.
"""

import json
from pathlib import Path

from web.backend.config import ANNOTATIONS_DIR, RAW_VIDEOS_DIR
from web.backend.models.schemas import AnnotationData, StrokeAnnotation
from web.backend.utils.video_converter import get_video_info


class AnnotationService:
    def load(self, video_id: str) -> AnnotationData | None:
        """
        Загружает разметку по video_id (stem).
        Файл: annotations/{video_id}.json
        """
        path = ANNOTATIONS_DIR / f"{video_id}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        raw.setdefault("video_id", video_id)
        # video может быть с любым расширением — оставляем как есть
        raw.setdefault("video", f"{video_id}.mp4")

        strokes = []
        for s in raw.get("strokes", []):
            strokes.append(StrokeAnnotation(**s))

        return AnnotationData(
            video_id=video_id,
            video=raw["video"],
            fps=raw.get("fps", 30),
            frames=raw.get("frames", 0),
            duration=raw.get("duration", 0),
            strokes=strokes,
            auto_detected=raw.get("auto_detected", False),
        )

    def save(self, video_id: str, data: AnnotationData):
        """Сохраняет разметку как annotations/{video_id}.json."""
        path = ANNOTATIONS_DIR / f"{video_id}.json"
        out = data.model_dump()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    def create_empty(self, video_id: str) -> AnnotationData:
        """Создаёт пустую разметку, определяя FPS из видео."""
        info = {"fps": 30, "total_frames": 0, "duration": 0}

        # Ищем видео в converted/ или raw_videos/
        for d in [RAW_VIDEOS_DIR]:
            for f in d.iterdir():
                if f.stem == video_id and f.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}:
                    try:
                        info = get_video_info(f)
                    except Exception:
                        pass
                    break

        data = AnnotationData(
            video_id=video_id,
            video=f"{video_id}.mp4",
            fps=info.get("fps", 30),
            frames=info.get("total_frames", 0),
            duration=info.get("duration", 0),
            strokes=[],
        )
        self.save(video_id, data)
        return data