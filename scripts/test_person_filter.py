"""
Тестирование фильтрации целевого игрока.
Запуск: python scripts/test_person_filter.py path/to/video.mp4

Создаёт debug-видео с визуализацией выбора игрока.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.features.person_filter import PersonFilter


def test_filter(video_path, output_path=None):
    """Прогоняет видео через PersonFilter и сохраняет debug-видео."""
    
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"Видео не найдено: {video_path}")
        return

    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_filter_debug.mp4"

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

    pf = PersonFilter(
        min_completeness=config.PERSON_FILTER['min_completeness'],
        max_center_shift=config.PERSON_FILTER['max_center_shift'],
        min_bbox_area=config.PERSON_FILTER['min_bbox_area'],
        crop_padding=config.PERSON_FILTER['crop_padding'],
    )
    pf.init(
        model_complexity=config.MEDIAPIPE['model_complexity'],
        min_detection_confidence=config.MEDIAPIPE['min_detection_confidence'],
        min_tracking_confidence=config.MEDIAPIPE['min_tracking_confidence'],
    )

    stats = {
        'total': 0, 'detected': 0,
        'tracking': 0, 'crop_recovery': 0,
        'initial_selection': 0, 'lost': 0, 'failed': 0,
    }

    print(f"Обработка {video_path.name} ({total} кадров)...")

    for idx in range(total):
        ret, frame = cap.read()
        if not ret:
            break

        landmarks, bbox, debug_info = pf.process_frame(frame)
        
        stats['total'] += 1
        method = debug_info.get('method', 'none')
        if method in stats:
            stats[method] += 1
        if debug_info.get('selected', False):
            stats['detected'] += 1

        # Рисуем debug
        vis = pf.draw_debug(frame, bbox, debug_info)
        
        # Добавляем скелет если есть
        if landmarks is not None:
            import mediapipe as mp
            mp_drawing = mp.solutions.drawing_utils
            mp_pose = mp.solutions.pose
            mp_drawing.draw_landmarks(
                vis, landmarks, mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 200, 0), thickness=1),
            )

        # Статистика на кадре
        cv2.putText(vis, f"Frame {idx}/{total}", (10, h - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        det_rate = stats['detected'] / max(stats['total'], 1) * 100
        cv2.putText(vis, f"Detection: {det_rate:.1f}%", (10, h - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(vis, f"Method: {method}", (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        writer.write(vis)

        if idx % 100 == 0:
            print(f"  {idx}/{total} ({idx/total*100:.0f}%)", end="\r")

    cap.release()
    writer.release()
    pf.close()

    print(f"\n\nГотово! Debug видео: {output_path}")
    print(f"\nСтатистика:")
    for k, v in stats.items():
        pct = v / max(stats['total'], 1) * 100
        print(f"  {k:20s}: {v:5d} ({pct:.1f}%)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python scripts/test_person_filter.py <video_path>")
        print("Пример: python scripts/test_person_filter.py data/raw_videos/game1.mp4")
        sys.exit(1)
    
    test_filter(sys.argv[1])