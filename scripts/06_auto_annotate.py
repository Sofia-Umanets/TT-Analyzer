#!/usr/bin/env python3
"""
ШАГ 6: Полуавтоматическая разметка нового видео.

Модель находит удары и определяет тип.
Вам остаётся добавить ошибки и проверить результат.

Запуск:
    python scripts/06_auto_annotate.py path/to/video.mp4
    python scripts/06_auto_annotate.py path/to/video.mp4 --output my_annotation.json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.features import PoseFeatureExtractor
from src.models.phase_detector import PhaseDetectorTrainer
from src.models.stroke_classifier import StrokeClassifierTrainer


def main():
    parser = argparse.ArgumentParser(
        description="Полуавтоматическая разметка видео")
    parser.add_argument('video', type=str, help='Путь к видео файлу')
    parser.add_argument('--output', type=str, default=None,
                        help='Путь для сохранения JSON')
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ОШИБКА: Видео не найдено: {video_path}")
        sys.exit(1)

    print("=" * 60)
    print("ПОЛУАВТОМАТИЧЕСКАЯ РАЗМЕТКА")
    print(f"Видео: {video_path.name}")
    print("=" * 60)

    # Загружаем модели
    phase_trainer = PhaseDetectorTrainer()
    phase_trainer.load()

    clf_trainer = StrokeClassifierTrainer()
    clf_trainer.load()

    # Извлекаем признаки
    print("\nИзвлечение признаков...")
    extractor = PoseFeatureExtractor()
    result = extractor.extract_full_video(video_path)
    # Если вернулось 5 значений (с фильтрацией), берём все, иначе — 4
    if len(result) == 5:
        features, landmarks, fps, det_mask, filter_stats = result
    else:
        features, landmarks, fps, det_mask = result
    #features, landmarks, fps, det_mask = extractor.extract_full_video(video_path)
    extractor.close()

    total_frames = len(features)
    duration = total_frames / fps
    print(f"  Кадров: {total_frames}, FPS: {fps:.1f}, "
          f"Длительность: {duration:.1f}с")

    # Детектируем фазы
    print("\nДетекция фаз...")
    phases, probs = phase_trainer.predict_video(features)
    strokes = phase_trainer.extract_strokes(phases, fps)

    print(f"Обнаружено ударов: {len(strokes)}")

    # Классифицируем каждый удар
    print("\nКлассификация типов...")
    for s in strokes:
        seg = features[s['start_frame']:s['end_frame'] + 1]
        if len(seg) >= 3:
            pred_type, type_probs = clf_trainer.predict(seg)
            confidence = type_probs.max()
        else:
            pred_type = 'other'
            confidence = 0.0

        s['type'] = pred_type
        s['type_confidence'] = round(float(confidence), 3)
        s['quality'] = 5  # Заполните вручную
        s['errors'] = []  # Заполните вручную

        print(f"  #{s['id']:2d} [{s['start_frame']:4d}→{s['contact_frame']:4d}→"
              f"{s['end_frame']:4d}] {pred_type:20s} "
              f"(conf: {confidence:.2f})")

    # Формируем JSON
    annotation = {
        'video': video_path.name,
        'fps': round(fps, 2),
        'frames': total_frames,
        'duration': round(duration, 2),
        'auto_detected': True,
        'detection_timestamp': datetime.now().isoformat(),
        'strokes': strokes,
    }

    # Сохраняем
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = config.ANNOTATIONS_DIR / f"{video_path.stem}_auto.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(annotation, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"✅ Аннотация сохранена: {out_path}")
    print(f"\n📝 Что нужно сделать вручную:")
    print(f"   1. Проверить start/contact/end кадры")
    print(f"   2. Проверить type (особенно если confidence < 0.7)")
    print(f"   3. Добавить errors для каждого удара")
    print(f"   4. Выставить quality (1-10)")
    print(f"   5. Переименовать файл (убрать _auto)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()