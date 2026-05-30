#!/usr/bin/env python3
"""
ШАГ 7: Полный анализ нового видео (все модели).

Запуск:
    python scripts/07_analyze_video.py path/to/video.mp4
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.features import PoseFeatureExtractor
from src.models.phase_detector import PhaseDetectorTrainer
from src.models.stroke_classifier import StrokeClassifierTrainer
from src.models.error_detector import ErrorDetectorTrainer
from src.utils.visualization import plot_phases


def main():
    parser = argparse.ArgumentParser(description="Полный анализ видео")
    parser.add_argument('video', type=str, help='Путь к видео')
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ОШИБКА: {video_path}")
        sys.exit(1)

    print("=" * 60)
    print("ПОЛНЫЙ АНАЛИЗ ВИДЕО")
    print(f"Видео: {video_path.name}")
    print("=" * 60)

    # Загружаем модели
    phase_trainer = PhaseDetectorTrainer()
    phase_trainer.load()

    clf_trainer = StrokeClassifierTrainer()
    clf_trainer.load()

    error_trainer = ErrorDetectorTrainer()
    has_errors = config.ERROR_MODEL_PATH.exists()
    if has_errors:
        error_trainer.load()

    # Извлекаем признаки
    print("\nИзвлечение признаков...")
    extractor = PoseFeatureExtractor()
    result = extractor.extract_full_video(video_path)
    if len(result) == 5:
        features, _, fps, _, _ = result
    else:
        features, _, fps, _ = result
    extractor.close()

    # Детекция фаз
    print("\nДетекция фаз...")
    phases, probs = phase_trainer.predict_video(features)
    strokes = phase_trainer.extract_strokes(phases, fps)

    # Анализ каждого удара
    print(f"\n{'='*60}")
    print(f"РЕЗУЛЬТАТЫ: {len(strokes)} ударов")
    print(f"{'='*60}")

    for s in strokes:
        seg = features[s['start_frame']:s['end_frame'] + 1]
        if len(seg) < 3:
            continue

        # Тип
        pred_type, type_probs = clf_trainer.predict(seg)
        s['type'] = pred_type

        # Ошибки
        if has_errors:
            # Получаем индекс типа для детектора ошибок
            type_idx = config.TYPE_TO_IDX.get(pred_type, 6)
            errors, quality, error_probs = error_trainer.predict(seg, stroke_type=type_idx)
            s['errors'] = errors
            s['quality'] = round(quality, 1)
        else:
            s['errors'] = []
            s['quality'] = None

        # Вывод
        errors_str = ', '.join(s['errors']) if s['errors'] else 'нет'
        q_str = f"{s['quality']:.1f}" if s['quality'] else '?'

        print(f"\n  Удар #{s['id']}")
        print(f"    Время: {s['start_time']:.2f}с → {s['contact_time']:.2f}с → "
              f"{s['end_time']:.2f}с")
        print(f"    Тип: {pred_type} (conf: {type_probs.max():.2f})")
        print(f"    Ошибки: {errors_str}")
        print(f"    Качество: {q_str}/10")

    # Визуализация
    plot_phases(
        features, phases, title=f"Analysis: {video_path.name}",
        save_path=config.OUTPUTS_DIR / f"analysis_{video_path.stem}.png")

    # Сохраняем результат
    result = {
        'video': video_path.name,
        'fps': round(fps, 2),
        'frames': len(features),
        'strokes': strokes,
    }
    result_path = config.OUTPUTS_DIR / f"analysis_{video_path.stem}.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Результат: {result_path}")


if __name__ == "__main__":
    main()