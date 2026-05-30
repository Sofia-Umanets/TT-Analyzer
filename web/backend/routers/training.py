"""Переобучение моделей и per-video статистика качества."""

import io
import sys
import json
import pickle
import traceback
import contextlib
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config as ml_config

router = APIRouter()

VALID_MODELS = {"classifier", "error_detector", "phase_detector"}


# ── schemas ───────────────────────────────────────────────────────────────────

class TrainingStatus(str, Enum):
    idle = "idle"
    running = "running"
    done = "done"
    error = "error"


class TrainingState(BaseModel):
    model: str
    status: TrainingStatus = TrainingStatus.idle
    progress: float = 0
    message: str = ""
    logs: list[str] = []
    metrics: dict = {}
    problem_videos: list[dict] = []


_state: dict[str, TrainingState] = {}


def _upd(model: str, progress: float = None, message: str = None, log: str = None):
    s = _state[model]
    if progress is not None:
        s.progress = progress
    if message is not None:
        s.message = message
    if log is not None:
        s.logs.append(log)


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{model}/run")
async def start_training(model: str, background_tasks: BackgroundTasks, request: Request):
    if model not in VALID_MODELS:
        raise HTTPException(400, f"model должен быть одним из: {', '.join(VALID_MODELS)}")
    if model in _state and _state[model].status == TrainingStatus.running:
        return _state[model]

    _state[model] = TrainingState(
        model=model, status=TrainingStatus.running,
        message="Загрузка данных...", logs=["Запуск обучения..."],
    )
    background_tasks.add_task(_train_task, model, request.app.state.ml)
    return _state[model]


@router.get("/{model}/progress")
async def get_progress(model: str):
    if model not in _state:
        return TrainingState(model=model, status=TrainingStatus.idle, message="Не запущено")
    return _state[model]


@router.get("/feature_importance")
async def get_feature_importance():
    """Возвращает глобальную важность признаков, вычисленную при последнем обучении классификатора."""
    path = ml_config.MODELS_DIR / "feature_importance.json"
    if not path.exists():
        raise HTTPException(404, "Важность признаков не вычислена. Запустите обучение классификатора.")
    with open(path) as f:
        return json.load(f)


@router.get("/stats")
async def get_stats(request: Request):
    """Пересчитывает per-video статистику для загруженных моделей без переобучения."""
    ml = request.app.state.ml

    if not ml_config.FEATURES_CACHE_PATH.exists():
        raise HTTPException(
            404,
            "Кэш признаков не найден. Запустите scripts/01_extract_features.py"
        )

    with open(ml_config.FEATURES_CACHE_PATH, "rb") as f:
        cache = pickle.load(f)

    per_video = cache.get("per_video", [])
    avail = ml.available_models()

    result = {
        "models_available": avail,
        "total_videos": len(per_video),
        "classifier": _clf_stats(ml._clf_trainer, per_video) if avail.get("stroke_classifier") else None,
        "error_detector": _err_stats(ml._error_trainer, per_video) if avail.get("error_detector") else None,
        "phase_detector": _phase_stats(ml._phase_trainer, per_video) if avail.get("phase_detector") else None,
    }
    return result


# ── background task ───────────────────────────────────────────────────────────

def _train_task(model: str, ml):
    try:
        if not ml_config.FEATURES_CACHE_PATH.exists():
            raise FileNotFoundError(f"Кэш признаков не найден: {ml_config.FEATURES_CACHE_PATH}")

        _upd(model, 5, "Загрузка кэша признаков...", "Загрузка кэша признаков...")

        with open(ml_config.FEATURES_CACHE_PATH, "rb") as f:
            cache = pickle.load(f)

        per_video = cache.get("per_video", [])
        _upd(model, 10, log=f"Загружено: {len(per_video)} видео")

        if model == "classifier":
            _run_classifier(model, ml, per_video)
        elif model == "error_detector":
            _run_error_detector(model, ml, per_video)
        else:
            _run_phase_detector(model, ml, per_video)

    except Exception as e:
        if model in _state:
            _state[model].status = TrainingStatus.error
            _state[model].message = str(e)
            _state[model].logs.append(f"ОШИБКА: {e}")
        traceback.print_exc()


def _run_classifier(model: str, ml, per_video: list):
    from src.models.stroke_classifier import StrokeClassifierTrainer
    from collections import Counter

    trainer = StrokeClassifierTrainer()
    samples = trainer.prepare_samples(per_video)

    if not samples:
        raise ValueError("Нет размеченных ударов для обучения")

    dist = Counter(s["type"] for s in samples)
    _upd(model, 15,
         f"Обучение на {len(samples)} ударах...",
         f"Собрано: {len(samples)} ударов — " + ", ".join(f"{t}:{c}" for t, c in sorted(dist.items())))

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        history = trainer.train(samples)

    for line in buf.getvalue().splitlines():
        if line.strip():
            _upd(model, log=line.strip())

    _upd(model, 85, "Сохранение модели...", "Сохранение модели...")
    trainer.save()
    ml._clf_trainer = trainer

    best_acc = max(history.get("val_acc", [0]))
    _upd(model, 90, "Вычисление статистики...",
         f"Готово. Лучшая Val Acc: {best_acc * 100:.1f}%")

    stats = _clf_stats(trainer, per_video)

    _state[model].status = TrainingStatus.done
    _state[model].progress = 100
    _state[model].message = "Готово"
    _state[model].metrics = {
        "best_val_acc": round(best_acc * 100, 1),
        "total_epochs": len(history.get("loss", [])),
        "total_strokes": stats["total_strokes"],
        "overall_accuracy": stats["overall_accuracy"],
    }
    _state[model].problem_videos = stats["videos"]
    _upd(model, log=f"Точность на аннотированных данных: {stats['overall_accuracy']}%")


def _run_error_detector(model: str, ml, per_video: list):
    from src.models.stroke_classifier import StrokeClassifierTrainer
    from src.models.error_detector import ErrorDetectorTrainer

    clf_trainer = StrokeClassifierTrainer()
    samples = clf_trainer.prepare_samples(per_video)

    if not samples:
        raise ValueError("Нет размеченных ударов для обучения")

    _upd(model, 15,
         f"Обучение на {len(samples)} ударах...",
         f"Собрано: {len(samples)} ударов")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        trainer = ErrorDetectorTrainer()
        history = trainer.train(samples)

    for line in buf.getvalue().splitlines():
        if line.strip():
            _upd(model, log=line.strip())

    _upd(model, 85, "Сохранение модели...", "Сохранение модели...")
    trainer.save()
    ml._error_trainer = trainer

    best_f1 = max(history.get("val_error_f1", [0]))
    _upd(model, 90, "Вычисление статистики...",
         f"Готово. Лучший Val F1: {best_f1:.3f}")

    stats = _err_stats(trainer, per_video)

    _state[model].status = TrainingStatus.done
    _state[model].progress = 100
    _state[model].message = "Готово"
    _state[model].metrics = {
        "best_val_f1": round(best_f1 * 100, 1),
        "total_epochs": len(history.get("loss", [])),
        "total_strokes": stats["total_strokes"],
    }
    _state[model].problem_videos = stats["videos"]

    f1_vals = [v["f1"] * 100 for v in stats["per_error_f1"].values() if v["support"] > 0]
    avg_f1 = sum(f1_vals) / len(f1_vals) if f1_vals else 0
    _upd(model, log=f"Средний F1 по ошибкам: {avg_f1:.1f}%")


# ── statistics helpers ────────────────────────────────────────────────────────

def _clf_stats(clf_trainer, per_video: list) -> dict:
    video_stats = []

    for v in per_video:
        info = v["info"]
        features = v["features"]
        correct = 0
        total = 0
        stroke_details = []

        for s in info.get("strokes", []):
            start = s["start_frame"]
            end = min(s["end_frame"], len(features) - 1)
            if end - start < 3:
                continue
            try:
                pred_type, _ = clf_trainer.predict(features[start:end + 1])
            except Exception:
                continue
            true_type = s.get("type", "other")
            ok = pred_type == true_type
            correct += ok
            total += 1
            stroke_details.append({
                "id": s.get("id"),
                "true": true_type,
                "pred": pred_type,
                "ok": ok,
            })

        acc = round(correct / total * 100, 1) if total > 0 else None
        video_stats.append({
            "video": info["video"],
            "n_strokes": total,
            "correct": correct,
            "accuracy": acc,
            "strokes": stroke_details,
        })

    video_stats.sort(key=lambda x: (x["accuracy"] is None, x["accuracy"] or 0))

    total_strokes = sum(v["n_strokes"] for v in video_stats)
    total_correct = sum(v["correct"] for v in video_stats)
    overall = round(total_correct / total_strokes * 100, 1) if total_strokes > 0 else 0

    return {
        "overall_accuracy": overall,
        "total_strokes": total_strokes,
        "videos": video_stats,
    }


def _err_stats(error_trainer, per_video: list) -> dict:
    import numpy as np

    all_pred, all_true = [], []
    video_stats = []

    for v in per_video:
        info = v["info"]
        features = v["features"]
        total = 0
        stroke_details = []

        for s in info.get("strokes", []):
            start = s["start_frame"]
            end = min(s["end_frame"], len(features) - 1)
            if end - start < 3:
                continue
            type_idx = ml_config.TYPE_TO_IDX.get(s.get("type", "other"), 6)
            try:
                pred_errors, _, _ = error_trainer.predict(features[start:end + 1], stroke_type=type_idx)
            except Exception:
                continue
            true_errors = s.get("errors", [])
            all_pred.append([1 if e in set(pred_errors) else 0 for e in ml_config.ERROR_TYPES])
            all_true.append([1 if e in set(true_errors) else 0 for e in ml_config.ERROR_TYPES])
            total += 1
            stroke_details.append({
                "id": s.get("id"),
                "true": true_errors,
                "pred": pred_errors,
            })

        video_stats.append({
            "video": info["video"],
            "n_strokes": total,
            "strokes": stroke_details,
        })

    per_error_f1 = {}
    if all_pred:
        p_arr = np.array(all_pred)
        t_arr = np.array(all_true)
        for i, name in enumerate(ml_config.ERROR_TYPES):
            tp = int(((p_arr[:, i] == 1) & (t_arr[:, i] == 1)).sum())
            fp = int(((p_arr[:, i] == 1) & (t_arr[:, i] == 0)).sum())
            fn = int(((p_arr[:, i] == 0) & (t_arr[:, i] == 1)).sum())
            pr = tp / (tp + fp + 1e-8)
            rc = tp / (tp + fn + 1e-8)
            f1 = 2 * pr * rc / (pr + rc + 1e-8)
            per_error_f1[name] = {"f1": round(float(f1), 3), "support": int(t_arr[:, i].sum())}

    return {
        "per_error_f1": per_error_f1,
        "total_strokes": sum(v["n_strokes"] for v in video_stats),
        "videos": video_stats,
    }


def _run_phase_detector(model: str, ml, per_video: list):
    from src.models.phase_detector import PhaseDetectorTrainer

    if not per_video:
        raise ValueError("Нет данных в кэше признаков")

    _upd(model, 15,
         f"Обучение на {len(per_video)} видео...",
         f"Видео в кэше: {len(per_video)}")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        trainer = PhaseDetectorTrainer()
        history = trainer.train(per_video)

    for line in buf.getvalue().splitlines():
        if line.strip():
            _upd(model, log=line.strip())

    _upd(model, 85, "Сохранение модели...", "Сохранение модели...")
    trainer.save()
    ml._phase_trainer = trainer

    best_f1 = max(history.get("val_f1", [0]))
    _upd(model, 90, "Вычисление статистики...",
         f"Готово. Лучший Val F1: {best_f1:.3f}")

    stats = _phase_stats(trainer, per_video)

    _state[model].status = TrainingStatus.done
    _state[model].progress = 100
    _state[model].message = "Готово"
    _state[model].metrics = {
        "best_val_f1": round(best_f1 * 100, 1),
        "total_epochs": len(history.get("loss", [])),
        "total_videos": len(per_video),
        "overall_accuracy": stats["overall_accuracy"],
    }
    _state[model].problem_videos = stats["videos"]
    _upd(model, log=f"Средняя точность по фазам: {stats['overall_accuracy']}%")


def _phase_stats(phase_trainer, per_video: list) -> dict:
    video_stats = []

    for v in per_video:
        info = v["info"]
        features = v["features"]
        labels = v["labels"]

        try:
            phases_pred, _ = phase_trainer.predict_video(features)
        except Exception:
            continue

        acc = float((phases_pred == labels).mean())

        phase_acc = {}
        for i, name in enumerate(ml_config.PHASE_NAMES):
            mask = labels == i
            if mask.sum() > 0:
                phase_acc[name] = round(float((phases_pred[mask] == i).mean()) * 100, 1)

        video_stats.append({
            "video": info["video"],
            "n_strokes": len(info.get("strokes", [])),
            "n_frames": len(features),
            "accuracy": round(acc * 100, 1),
            "phase_acc": phase_acc,
        })

    video_stats.sort(key=lambda x: x["accuracy"])
    overall = (
        sum(v["accuracy"] for v in video_stats) / len(video_stats)
        if video_stats else 0
    )

    return {
        "overall_accuracy": round(overall, 1),
        "total_frames": sum(v["n_frames"] for v in video_stats),
        "total_videos": len(video_stats),
        "videos": video_stats,
    }
