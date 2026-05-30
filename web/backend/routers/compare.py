"""Сравнение ударов из разных видео."""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config as ml_config
from web.backend.config import CACHE_DIR, ANALYSIS_CACHE_DIR, ANNOTATIONS_DIR

router = APIRouter()


# ── schemas ───────────────────────────────────────────────────────────────────

class StrokeRef(BaseModel):
    video_id: str
    stroke_id: int


class CompareRequest(BaseModel):
    strokes: list[StrokeRef]
    normalize: bool = False


# ── endpoint ──────────────────────────────────────────────────────────────────

@router.post("/")
def compare_strokes(req: CompareRequest):
    if len(req.strokes) < 2:
        raise HTTPException(400, "Нужно минимум 2 удара для сравнения")
    if len(req.strokes) > 3:
        raise HTTPException(400, "Максимум 3 удара для сравнения")

    results = [_get_stroke_data(ref.video_id, ref.stroke_id, req.normalize) for ref in req.strokes]
    return {"strokes": results, "normalize": req.normalize}


# ── data helpers ──────────────────────────────────────────────────────────────

def _get_stroke_data(video_id: str, stroke_id: int, normalize: bool) -> dict:
    meta = _find_stroke_meta(video_id, stroke_id)
    if meta is None:
        return {"video_id": video_id, "stroke_id": stroke_id, "error": "Удар не найден", "frames": None}

    features = _load_stroke_features(video_id, meta)

    if features is not None and normalize and len(features) > 3:
        from src.data.preprocessing import normalize_sequence
        features = normalize_sequence(features, 100)

    frames_data = None
    if features is not None and len(features) > 0:
        frames_data = []
        for i, row in enumerate(features):
            d = {}
            for j, name in enumerate(ml_config.FEATURE_NAMES):
                if j < len(row):
                    d[name] = round(float(row[j]), 4)
            frames_data.append({"frame_idx": i, "features": d})

    return {"video_id": video_id, **meta, "frames": frames_data}


def _find_stroke_meta(video_id: str, stroke_id: int) -> dict | None:
    # 1. Результат анализа (предпочтительно — predicted_type, float quality)
    analysis_path = ANALYSIS_CACHE_DIR / f"{video_id}.json"
    if analysis_path.exists():
        try:
            with open(analysis_path) as f:
                data = json.load(f)
            s = next((s for s in data.get("strokes", []) if s["id"] == stroke_id), None)
            if s:
                return {
                    "stroke_id":    stroke_id,
                    "type":         s.get("predicted_type") or s.get("type", "other"),
                    "quality":      s.get("quality"),
                    "errors":       s.get("errors", []),
                    "start_frame":  s.get("start_frame"),
                    "contact_frame": s.get("contact_frame"),
                    "end_frame":    s.get("end_frame"),
                    "start_time":   s.get("start_time"),
                    "contact_time": s.get("contact_time"),
                    "end_time":     s.get("end_time"),
                    "duration":     _calc_duration(s),
                    "source":       "analysis",
                }
        except Exception:
            pass

    # 2. Разметка (manual → auto)
    for fname in (f"{video_id}.json", f"{video_id}_auto.json"):
        ann_path = ANNOTATIONS_DIR / fname
        if not ann_path.exists():
            continue
        try:
            with open(ann_path) as f:
                data = json.load(f)
            s = next((s for s in data.get("strokes", []) if s["id"] == stroke_id), None)
            if s:
                fps = data.get("fps", 30) or 30
                st = s.get("start_time") or round(s.get("start_frame", 0) / fps, 3)
                et = s.get("end_time")   or round(s.get("end_frame",   0) / fps, 3)
                ct = s.get("contact_time") or (
                    round(s.get("contact_frame", 0) / fps, 3) if s.get("contact_frame") else None
                )
                return {
                    "stroke_id":    stroke_id,
                    "type":         s.get("type", "other"),
                    "quality":      s.get("quality"),
                    "errors":       s.get("errors", []),
                    "start_frame":  s.get("start_frame"),
                    "contact_frame": s.get("contact_frame"),
                    "end_frame":    s.get("end_frame"),
                    "start_time":   round(st, 3),
                    "contact_time": ct,
                    "end_time":     round(et, 3),
                    "duration":     round(et - st, 3),
                    "source":       "annotation",
                }
        except Exception:
            pass

    return None


def _load_stroke_features(video_id: str, meta: dict) -> np.ndarray | None:
    start = meta.get("start_frame")
    end   = meta.get("end_frame")
    if start is None or end is None:
        return None

    # 1. .npy — создаётся при анализе
    npy_path = CACHE_DIR / f"{video_id}_features.npy"
    if npy_path.exists():
        try:
            all_feat = np.load(str(npy_path))
            return all_feat[start:min(end + 1, len(all_feat))]
        except Exception:
            pass

    # 2. features_cache.pkl — создаётся при извлечении признаков
    if ml_config.FEATURES_CACHE_PATH.exists():
        try:
            with open(ml_config.FEATURES_CACHE_PATH, "rb") as f:
                cache = pickle.load(f)
            for v in cache.get("per_video", []):
                if Path(v["info"]["video"]).stem == video_id:
                    feat = v["features"]
                    return feat[start:min(end + 1, len(feat))]
        except Exception:
            pass

    return None


def _calc_duration(stroke: dict) -> float | None:
    st, et = stroke.get("start_time"), stroke.get("end_time")
    if st is not None and et is not None:
        return round(et - st, 3)
    sf, ef = stroke.get("start_frame"), stroke.get("end_frame")
    if sf is not None and ef is not None:
        return ef - sf
    return None
