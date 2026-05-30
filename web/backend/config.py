"""
Конфигурация веб-приложения.
Работаем напрямую с raw_videos/ и annotations/ — без дублирования.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
WEB_ROOT = Path(__file__).parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_VIDEOS_DIR = DATA_DIR / "raw_videos"
ANNOTATIONS_DIR = DATA_DIR / "annotations"
CACHE_DIR = DATA_DIR / "cache"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Веб-специфичные
UPLOAD_DIR = DATA_DIR / "uploads"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
ANALYSIS_CACHE_DIR = CACHE_DIR / "analysis"

for d in [RAW_VIDEOS_DIR, ANNOTATIONS_DIR, UPLOAD_DIR,
          THUMBNAILS_DIR, ANALYSIS_CACHE_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

VIDEO_CONVERT = {
    "video_codec": "libx264",
    "audio_codec": "aac",
    "crf": 26,        # 23→26: визуально неотличимо, -25% размер
    "preset": "fast",
    # Масштабирование ОТКЛЮЧЕНО: scale ломает velocity/acceleration признаки
    # (производные от позиций → малый jitter × умножение → MAE 100-230).
    # Модели обучены на признаках из оригинального разрешения.
    "max_dimension": 0,
}

HOST = "0.0.0.0"
PORT = 8000
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

MAX_UPLOAD_SIZE_MB = 500

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',
                    '.MP4', '.MOV', '.AVI', '.MKV', '.WMV'}