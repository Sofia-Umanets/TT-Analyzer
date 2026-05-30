"""Данные для визуализации."""

import json
import numpy as np
from fastapi import APIRouter, HTTPException, Request, Query
from web.backend.config import ANALYSIS_CACHE_DIR, CACHE_DIR

router = APIRouter()


@router.get("/{video_id}/features")
async def get_features_range(video_id: str, start: int = Query(0, ge=0), end: int = Query(100), step: int = Query(1, ge=1)):
    path = CACHE_DIR / f"{video_id}_features.npy"
    if not path.exists():
        raise HTTPException(404, "Признаки не найдены")
    features = np.load(str(path))
    end = min(end, len(features))
    import config as ml_config
    result = []
    for i in range(start, end, step):
        d = {}
        for j, name in enumerate(ml_config.FEATURE_NAMES):
            if j < features.shape[1]:
                d[name] = round(float(features[i, j]), 4)
        result.append({"frame": i, "features": d})
    return {"frames": result, "total": len(features)}


@router.get("/{video_id}/landmarks")
async def get_all_landmarks(video_id: str):
    """Возвращает все landmarks сразу для client-side кэширования."""
    path = CACHE_DIR / f"{video_id}_landmarks.json"
    if not path.exists():
        raise HTTPException(404, "Landmarks не найдены")
    with open(path, "r") as f:
        all_lm = json.load(f)
    return {"video_id": video_id, "total_frames": len(all_lm), "landmarks": all_lm}


@router.get("/{video_id}/skeleton/{frame}")
async def get_skeleton(video_id: str, frame: int):
    path = CACHE_DIR / f"{video_id}_landmarks.json"
    if not path.exists():
        raise HTTPException(404, "Landmarks не найдены")
    with open(path, "r") as f:
        all_lm = json.load(f)
    if frame < 0 or frame >= len(all_lm):
        raise HTTPException(400, f"Кадр {frame} вне диапазона")
    lm = all_lm[frame]
    connections = [
        ["left_shoulder", "right_shoulder"],
        ["left_shoulder", "left_elbow"], ["left_elbow", "left_wrist"],
        ["right_shoulder", "right_elbow"], ["right_elbow", "right_wrist"],
        ["left_shoulder", "left_hip"], ["right_shoulder", "right_hip"],
        ["left_hip", "right_hip"],
        ["left_hip", "left_knee"], ["left_knee", "left_ankle"],
        ["right_hip", "right_knee"], ["right_knee", "right_ankle"],
    ]
    if lm is None:
        return {"frame": frame, "landmarks": None, "connections": connections, "detected": False}
    return {"frame": frame, "landmarks": lm, "connections": connections, "detected": True}


@router.get("/{video_id}/stroke/{stroke_id}/attention")
async def get_stroke_attention(video_id: str, stroke_id: int, request: Request):
    path = ANALYSIS_CACHE_DIR / f"{video_id}.json"
    if not path.exists():
        raise HTTPException(404, "Анализ не найден")
    with open(path, "r") as f:
        analysis = json.load(f)
    stroke = next((s for s in analysis["strokes"] if s["id"] == stroke_id), None)
    if not stroke:
        raise HTTPException(404, f"Удар {stroke_id} не найден")
    ml = request.app.state.ml
    return ml.compute_attention(video_id, stroke)


@router.get("/{video_id}/stroke/{stroke_id}/features")
async def get_stroke_features(video_id: str, stroke_id: int):
    result_path = ANALYSIS_CACHE_DIR / f"{video_id}.json"
    features_path = CACHE_DIR / f"{video_id}_features.npy"
    if not result_path.exists() or not features_path.exists():
        raise HTTPException(404, "Анализ не найден")
    with open(result_path, "r") as f:
        analysis = json.load(f)
    stroke = next((s for s in analysis["strokes"] if s["id"] == stroke_id), None)
    if not stroke:
        raise HTTPException(404, f"Удар {stroke_id} не найден")
    features = np.load(str(features_path))
    start = stroke["start_frame"]
    end = min(stroke["end_frame"] + 1, len(features))
    import config as ml_config
    frames_data = []
    for i, row in enumerate(features[start:end]):
        d = {}
        for j, name in enumerate(ml_config.FEATURE_NAMES):
            if j < len(row):
                d[name] = round(float(row[j]), 4)
        frames_data.append({
            "frame": start + i,
            "phase": int(analysis["phases"][start + i]) if start + i < len(analysis["phases"]) else 0,
            "features": d,
        })
    return {"stroke_id": stroke_id, "start_frame": start, "end_frame": end - 1, "frames": frames_data}