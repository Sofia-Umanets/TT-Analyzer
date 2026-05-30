"""Метрики качества для всех задач."""

import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config


def evaluate_phase_detection(per_video, phase_trainer):
    """
    Оценивает качество детекции фаз: сравнивает найденные удары с ground truth.

    Returns
    -------
    results : dict
    """
    print("\n" + "=" * 60)
    print("ОЦЕНКА ДЕТЕКЦИИ ФАЗ")
    print("=" * 60)

    start_errors, contact_errors, end_errors = [], [], []
    total_true = 0
    total_detected = 0
    total_matched = 0

    for v in per_video:
        features = v['features']
        info = v['info']
        true_strokes = info['strokes']
        fps = info['fps']

        phases, probs = phase_trainer.predict_video(features)
        pred_strokes = phase_trainer.extract_strokes(phases, fps)

        total_true += len(true_strokes)
        total_detected += len(pred_strokes)

        for ts in true_strokes:
            tc = ts['contact_frame']
            best = None
            best_d = float('inf')

            for ps in pred_strokes:
                d = abs(ps['contact_frame'] - tc)
                if d < best_d:
                    best_d = d
                    best = ps

            if best is not None and best_d <= 10:
                total_matched += 1
                start_errors.append(abs(best['start_frame'] - ts['start_frame']))
                contact_errors.append(abs(best['contact_frame'] - ts['contact_frame']))
                end_errors.append(abs(best['end_frame'] - ts['end_frame']))

        print(f"  {info['video']}: true={len(true_strokes)}, "
              f"detected={len(pred_strokes)}")

    precision = total_matched / (total_detected + 1e-8)
    recall = total_matched / (total_true + 1e-8)
    f1 = 2 * precision * recall / (precision + recall + 1e-8)

    results = {
        'total_true': total_true,
        'total_detected': total_detected,
        'total_matched': total_matched,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'start_mae': np.mean(start_errors) if start_errors else None,
        'contact_mae': np.mean(contact_errors) if contact_errors else None,
        'end_mae': np.mean(end_errors) if end_errors else None,
    }

    print(f"\n  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1:        {f1:.3f}")

    if start_errors:
        avg_fps = np.mean([v['info']['fps'] for v in per_video])
        print(f"\n  Start MAE:   {np.mean(start_errors):.1f} кадров "
              f"(±{np.mean(start_errors)/avg_fps*1000:.0f} мс)")
        print(f"  Contact MAE: {np.mean(contact_errors):.1f} кадров "
              f"(±{np.mean(contact_errors)/avg_fps*1000:.0f} мс)")
        print(f"  End MAE:     {np.mean(end_errors):.1f} кадров "
              f"(±{np.mean(end_errors)/avg_fps*1000:.0f} мс)")

    return results


def evaluate_classification(per_video, classifier_trainer, phase_trainer):
    """
    Оценивает классификацию типов на автоматически найденных ударах.
    """
    print("\n" + "=" * 60)
    print("ОЦЕНКА КЛАССИФИКАЦИИ ТИПОВ")
    print("=" * 60)

    correct = 0
    total = 0

    for v in per_video:
        features = v['features']
        info = v['info']
        true_strokes = info['strokes']
        fps = info['fps']

        phases, _ = phase_trainer.predict_video(features)
        pred_strokes = phase_trainer.extract_strokes(phases, fps)

        for ts in true_strokes:
            tc = ts['contact_frame']
            best = None
            best_d = float('inf')

            for ps in pred_strokes:
                d = abs(ps['contact_frame'] - tc)
                if d < best_d:
                    best_d = d
                    best = ps

            if best is not None and best_d <= 10:
                seg = features[best['start_frame']:best['end_frame'] + 1]
                if len(seg) < 3:
                    continue

                pred_type, _ = classifier_trainer.predict(seg)
                true_type = ts.get('type', 'other')

                if pred_type == true_type:
                    correct += 1
                total += 1

    acc = correct / total if total > 0 else 0
    print(f"  Accuracy (на авто-сегментах): {acc:.3f} ({correct}/{total})")
    return acc