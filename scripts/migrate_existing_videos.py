"""
Импорт существующих видео из data/raw_videos в индекс, без конвертации.
Запуск: python scripts/migrate_existing_videos.py
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.backend.config import RAW_VIDEOS_DIR, THUMBNAILS_DIR
from web.backend.utils.video_converter import get_video_info, generate_thumbnail


def main():
    extensions = {'.mp4', '.mov', '.avi', '.mkv', '.MP4', '.MOV', '.AVI', '.MKV'}
    index_path = RAW_VIDEOS_DIR / "_videos_index.json"
    db = {}

    # Загружаем существующий индекс, если есть
    if index_path.exists():
        with open(index_path, "r") as f:
            db = json.load(f)

    imported = 0
    for video_path in RAW_VIDEOS_DIR.glob("*"):
        if video_path.suffix not in extensions:
            continue
        video_id = video_path.stem
        if video_id in db:
            print(f"Пропуск: {video_path.name} (уже в индексе)")
            continue

        print(f"Импорт: {video_path.name}")

        # Получаем метаданные
        info = get_video_info(video_path)
        # Генерируем превью
        thumb_path = THUMBNAILS_DIR / f"{video_id}.jpg"
        if not thumb_path.exists():
            generate_thumbnail(video_path, thumb_path)

        db[video_id] = {
            "id": video_id,
            "filename": video_path.name,
            "original_name": video_path.name,
            "status": "ready",
            "fps": info["fps"],
            "total_frames": info["total_frames"],
            "duration": info["duration"],
            "width": info["width"],
            "height": info["height"],
            "size_mb": round(video_path.stat().st_size / 1024 / 1024, 2),
            "created_at": video_path.stat().st_mtime,
            "converted": False,
        }
        imported += 1

    with open(index_path, "w") as f:
        json.dump(db, f, indent=2)

    print(f"\nИмпортировано {imported} видео. Всего в индексе: {len(db)}")
    print(f"Индекс сохранён: {index_path}")


if __name__ == "__main__":
    main()