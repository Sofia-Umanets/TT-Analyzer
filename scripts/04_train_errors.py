#!/usr/bin/env python3
"""
ШАГ 4: Обучение детектора ошибок техники.

Запуск:
    python scripts/04_train_errors.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.data.preprocessing import load_cache
from src.models.stroke_classifier import StrokeClassifierTrainer
from src.models.error_detector import ErrorDetectorTrainer
from src.utils.visualization import plot_training_history


def main():
    print("=" * 60)
    print("ШАГ 4: ОБУЧЕНИЕ ДЕТЕКТОРА ОШИБОК")
    print("=" * 60)

    cache = load_cache()
    per_video = cache['per_video']

    # Используем те же samples что и для классификатора
    clf_trainer = StrokeClassifierTrainer()
    samples = clf_trainer.prepare_samples(per_video)

    trainer = ErrorDetectorTrainer()
    history = trainer.train(samples)
    trainer.save()

    plot_training_history(
        history,
        title="Error Detector Training",
        save_path=config.OUTPUTS_DIR / "error_training.png")

    print("\nГотово!")


if __name__ == "__main__":
    main()