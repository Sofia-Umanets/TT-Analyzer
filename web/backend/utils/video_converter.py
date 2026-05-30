"""
Конвертация видео в MP4 (H.264) БЕЗ изменения FPS и разрешения.
"""

import subprocess
import json
import shutil
from pathlib import Path

from web.backend.config import VIDEO_CONVERT


def get_video_info(path: Path) -> dict:
    """Получить метаданные видео."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr[:200]}")
        data = json.loads(result.stdout)
    except Exception as e:
        print(f"[get_video_info] ffprobe не сработал ({e}), пробуем OpenCV...")
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"Не удалось открыть видео: {path}")
        info = {
            "fps": cap.get(cv2.CAP_PROP_FPS) or 30,
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration": 0,
        }
        if info["fps"] > 0 and info["total_frames"] > 0:
            info["duration"] = round(info["total_frames"] / info["fps"], 2)
        cap.release()
        return info

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )

    if video_stream is None:
        raise ValueError("Видеопоток не найден в файле")

    # FPS
    fps_str = video_stream.get("r_frame_rate", "30/1")
    fps_parts = fps_str.split("/")
    if len(fps_parts) == 2 and float(fps_parts[1]) > 0:
        fps = float(fps_parts[0]) / float(fps_parts[1])
    else:
        fps = 30.0

    duration = float(data.get("format", {}).get("duration", 0))
    total_frames = int(video_stream.get("nb_frames", 0))
    if total_frames == 0 and fps > 0 and duration > 0:
        total_frames = int(duration * fps)

    return {
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "duration": round(duration, 2),
    }


def convert_video(input_path: Path, output_path: Path, make_keyframes: bool = False) -> Path:
    """
    Конвертирует видео в MP4 (H.264).
    Масштабирует до max_dimension (config), НЕ меняет FPS.
    output_path ДОЛЖЕН иметь расширение .mp4.

    make_keyframes=True: I-frame каждые 12 кадров — быстрый seek в браузере.
    Для видео с разметкой — False, чтобы не сдвинуть кадровые метки S/C/E.
    """
    cfg = VIDEO_CONVERT

    # Убеждаемся что выходной файл — .mp4
    output_path = output_path.with_suffix(".mp4")

    print(f"[Конвертация] {input_path.name} -> {output_path.name}"
          f"{' [keyframes]' if make_keyframes else ''}")
    print(f"  Вход: {input_path} ({input_path.stat().st_size / 1024 / 1024:.1f} МБ)")

    # Проверяем что ffmpeg доступен
    try:
        check = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        if check.returncode != 0:
            raise RuntimeError("ffmpeg не найден")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg не установлен. Установите: sudo apt install ffmpeg")

    # I-frame каждые 12 кадров: seek ≤ 0.2с при 60fps, файл значительно меньше чем -g 1
    keyframe_flags = ["-g", "12", "-keyint_min", "12"] if make_keyframes else []

    # Масштабирование: длинная сторона обрезается до max_dimension.
    # 4K portrait (2160×3840) → 1080×1920; Full HD — без изменений.
    # -vsync 0 гарантирует точное число кадров, scale не влияет на это.
    max_dim = cfg.get("max_dimension", 0)
    scale_flags = (
        ["-vf", f"scale={max_dim}:{max_dim}:force_original_aspect_ratio=decrease:force_divisible_by=2"]
        if max_dim > 0 else []
    )

    # Основная команда: перекодируем видео + аудио
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-c:v", cfg["video_codec"],
        "-preset", cfg["preset"],
        "-crf", str(cfg["crf"]),
        *scale_flags,
        *keyframe_flags,
        "-vsync", "0",               # сохраняем исходный FPS и количество кадров
        "-c:a", cfg["audio_codec"],
        "-b:a", "128k",
        "-movflags", "+faststart",   # для стриминга в браузере
        "-pix_fmt", "yuv420p",       # совместимость с браузерами
        str(output_path),
    ]

    print(f"  Команда: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)

    if result.returncode != 0:
        print(f"  [WARN] ffmpeg с аудио не удался, пробуем без аудио...")
        print(f"  stderr: {result.stderr[-300:]}")

        # Пробуем без аудио
        cmd_no_audio = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c:v", cfg["video_codec"],
            "-preset", cfg["preset"],
            "-crf", str(cfg["crf"]),
            *scale_flags,
            *keyframe_flags,
            "-vsync", "0",
            "-an",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]

        result2 = subprocess.run(cmd_no_audio, capture_output=True, text=True, timeout=1200)

        if result2.returncode != 0:
            print(f"  [ERROR] ffmpeg stderr: {result2.stderr[-500:]}")
            raise RuntimeError(
                f"ffmpeg не смог сконвертировать видео.\n"
                f"Вход: {input_path.name}\n"
                f"Ошибка: {result2.stderr[-300:]}"
            )

    if not output_path.exists():
        raise RuntimeError(f"Выходной файл не создан: {output_path}")

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  Готово: {output_path.name} ({size_mb:.1f} МБ)")

    return output_path


def is_mp4_h264(path: Path) -> bool:
    """Проверяет, является ли файл уже MP4 с кодеком H.264 — чтобы не перекодировать лишний раз."""
    if path.suffix.lower() != '.mp4':
        return False
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)
        vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        return vs is not None and vs.get("codec_name") == "h264"
    except Exception:
        return False


def generate_thumbnail(video_path: Path, output_path: Path, time_sec: float = 1.0):
    """Генерирует превью из видео."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_sec),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "scale=320:-1",
        "-q:v", "5",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except Exception as e:
        print(f"  [WARN] Не удалось создать превью: {e}")