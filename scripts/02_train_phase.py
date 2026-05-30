#!/usr/bin/env python3
"""
ШАГ 2: Обучение детектора фаз удара.

Запуск:
    python scripts/02_train_phase.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.data.preprocessing import load_cache
from src.models.phase_detector import PhaseDetectorTrainer
from src.utils.visualization import plot_phases, plot_training_history
from src.utils.metrics import evaluate_phase_detection


def main():
    print("=" * 60)
    print("ШАГ 2: ОБУЧЕНИЕ ДЕТЕКТОРА ФАЗ")
    print("=" * 60)

    # Загружаем кэш
    cache = load_cache()
    per_video = cache['per_video']
    print(f"Видео: {len(per_video)}")

    # Обучаем
    trainer = PhaseDetectorTrainer()
    history = trainer.train(per_video)
    trainer.save()

    # Визуализация обучения
    plot_training_history(
        history,
        title="Phase Detector Training",
        save_path=config.OUTPUTS_DIR / "phase_training.png")

    # Оцениваем только на видео, которые модель не видела при обучении.
    # trainer._val_per_video заполняется внутри train() и равен всем видео,
    # если датасет слишком мал для разбивки (n <= 3).
    eval_videos = trainer._val_per_video if trainer._val_per_video else per_video
    print(f"\nОценка на {len(eval_videos)} val-видео "
          f"({'отложенная выборка' if eval_videos is not per_video else 'все видео (мало данных)'}):")
    results = evaluate_phase_detection(eval_videos, trainer)

    # Визуализация фаз для каждого видео
    for i, v in enumerate(per_video):
        phases, _ = trainer.predict_video(v['features'])
        plot_phases(
            v['features'], phases, v['labels'],
            title=f"Phases: {v['info']['video']}",
            save_path=config.OUTPUTS_DIR / f"phases_video_{i+1}.png")

    print("\nГотово!")


if __name__ == "__main__":
    main()