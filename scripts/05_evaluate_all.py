#!/usr/bin/env python3
"""
ШАГ 5: Полная оценка всех моделей.

Запуск:
    python scripts/05_evaluate_all.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.data.preprocessing import load_cache
from src.models.phase_detector import PhaseDetectorTrainer
from src.models.stroke_classifier import StrokeClassifierTrainer
from src.models.error_detector import ErrorDetectorTrainer
from src.utils.metrics import evaluate_phase_detection, evaluate_classification
from src.utils.visualization import plot_phases


def main():
    print("=" * 60)
    print("ШАГ 5: ПОЛНАЯ ОЦЕНКА ВСЕХ МОДЕЛЕЙ")
    print("=" * 60)
    print("ВНИМАНИЕ: оценка проводится на всём датасете, включая обучающие")
    print("видео. Это даёт представление об общей картине, но метрики")
    print("завышены. Честные val-метрики смотри в логах обучения (шаги 2-4).")
    print("=" * 60)

    cache = load_cache()
    per_video = cache['per_video']

    # Загружаем модели
    phase_trainer = PhaseDetectorTrainer()
    phase_trainer.load()

    clf_trainer = StrokeClassifierTrainer()
    clf_trainer.load()

    error_trainer = ErrorDetectorTrainer()
    if config.ERROR_MODEL_PATH.exists():
        error_trainer.load()
    else:
        print("  ⚠ Модель ошибок не найдена, пропускаем")
        error_trainer = None

    # 1. Детекция фаз — полный датасет (включая обучающие видео)
    phase_results = evaluate_phase_detection(per_video, phase_trainer)

    # 2. Классификация ударов — полный датасет
    clf_acc = evaluate_classification(per_video, clf_trainer, phase_trainer)

    # 3. Подробный отчёт по каждому видео
    print("\n" + "=" * 60)
    print("ПОДРОБНЫЙ ОТЧЁТ ПО ВИДЕО")
    print("=" * 60)

    for i, v in enumerate(per_video):
        features = v['features']
        info = v['info']
        fps = info['fps']
        true_strokes = info['strokes']

        print(f"\n{'─'*50}")
        print(f"Видео: {info['video']}")
        print(f"{'─'*50}")

        # Детекция фаз
        phases, probs = phase_trainer.predict_video(features)
        pred_strokes = phase_trainer.extract_strokes(phases, fps)

        print(f"  Ударов: true={len(true_strokes)}, detected={len(pred_strokes)}")

        # Для каждого найденного удара
        for ps in pred_strokes:
            seg = features[ps['start_frame']:ps['end_frame'] + 1]
            if len(seg) < 3:
                continue

            pred_type, type_probs = clf_trainer.predict(seg)

            # Ищем соответствующий true stroke
            matched_true = None
            for ts in true_strokes:
                if abs(ts['contact_frame'] - ps['contact_frame']) <= 10:
                    matched_true = ts
                    break

            true_type = matched_true['type'] if matched_true else '?'
            match_mark = '✓' if pred_type == true_type else '✗'

            errors_str = ""
            if error_trainer and error_trainer.model:
                errors, quality, _ = error_trainer.predict(seg)
                errors_str = f" | errors={errors} q={quality:.1f}"

            print(f"  #{ps['id']:2d} [{ps['start_frame']:4d}→"
                  f"{ps['contact_frame']:4d}→{ps['end_frame']:4d}] "
                  f"type: {pred_type:20s} (true: {true_type:20s}) "
                  f"{match_mark}{errors_str}")

        # Визуализация
        plot_phases(
            features, phases, v['labels'],
            title=f"Evaluation: {info['video']}",
            save_path=config.OUTPUTS_DIR / f"eval_video_{i+1}.png")

    # Итог
    print("\n" + "=" * 60)
    print("ИТОГОВЫЕ МЕТРИКИ")
    print("=" * 60)
    print(f"  Детекция фаз F1:    {phase_results['f1']:.3f}")
    print(f"  Классификация Acc:   {clf_acc:.3f}")
    if phase_results['contact_mae'] is not None:
        print(f"  Contact MAE:         {phase_results['contact_mae']:.1f} кадров")

    # Сохраняем отчёт
    report = {
        'phase_detection': phase_results,
        'classification_accuracy': clf_acc,
    }
    report_path = config.OUTPUTS_DIR / "evaluation_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Отчёт: {report_path}")


if __name__ == "__main__":
    main()