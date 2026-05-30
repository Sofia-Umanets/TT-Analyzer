#!/usr/bin/env python3
"""
ШАГ 3: Обучение классификатора типов ударов.

Запуск:
    python scripts/03_train_classifier.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.data.preprocessing import load_cache
from src.models.stroke_classifier import StrokeClassifierTrainer
from src.utils.visualization import plot_training_history


def main():
    print("=" * 60)
    print("ШАГ 3: ОБУЧЕНИЕ КЛАССИФИКАТОРА ТИПОВ")
    print("=" * 60)

    cache = load_cache()
    per_video = cache['per_video']

    trainer = StrokeClassifierTrainer()
    samples = trainer.prepare_samples(per_video)
    history = trainer.train(samples)
    trainer.save()

    plot_training_history(
        history,
        title="Stroke Classifier Training",
        save_path=config.OUTPUTS_DIR / "classifier_training.png")

    print("\nГотово!")


if __name__ == "__main__":
    main()