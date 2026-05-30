"""
Мост между веб-приложением и ML-моделями.
"""

import sys
import json
import numpy as np
from pathlib import Path
from typing import Callable, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config as ml_config
from web.backend.config import CACHE_DIR, ANALYSIS_CACHE_DIR, ANNOTATIONS_DIR, RAW_VIDEOS_DIR


class MLBridge:
    def __init__(self):
        self._phase_trainer = None
        self._clf_trainer = None
        self._error_trainer = None
        self._loaded = False

    def load_models(self):
        import torch
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        if torch.cuda.is_available():
            print(f"[ML Bridge] GPU: {torch.cuda.get_device_name(0)} "
                  f"({torch.cuda.get_device_properties(0).total_memory // 1024**2} MB)")
        else:
            print("[ML Bridge] GPU не доступен, используется CPU")
        print(f"[ML Bridge] Загрузка моделей на {device}...")

        try:
            from src.models.phase_detector import PhaseDetectorTrainer
            if ml_config.PHASE_MODEL_PATH.exists():
                self._phase_trainer = PhaseDetectorTrainer()
                self._phase_trainer.load()
                print("  ✓ Детектор фаз загружен")
        except Exception as e:
            print(f"  ✗ Детектор фаз: {e}")

        try:
            from src.models.stroke_classifier import StrokeClassifierTrainer
            if ml_config.CLASSIFIER_MODEL_PATH.exists():
                self._clf_trainer = StrokeClassifierTrainer()
                self._clf_trainer.load()
                print("  ✓ Классификатор типов загружен")
        except Exception as e:
            print(f"  ✗ Классификатор типов: {e}")

        try:
            from src.models.error_detector import ErrorDetectorTrainer
            if ml_config.ERROR_MODEL_PATH.exists():
                self._error_trainer = ErrorDetectorTrainer()
                self._error_trainer.load()
                print("  ✓ Детектор ошибок загружен")
        except Exception as e:
            print(f"  ✗ Детектор ошибок: {e}")

        self._loaded = True
        print("[ML Bridge] Готов")

    def is_loaded(self) -> bool:
        return self._loaded

    def available_models(self) -> dict:
        return {
            "phase_detector": self._phase_trainer is not None,
            "stroke_classifier": self._clf_trainer is not None,
            "error_detector": self._error_trainer is not None,
        }

    def cleanup(self):
        pass

    def _find_video_path(self, video_path: Path) -> Path:
        """
        Находит реальный путь к видео.
        video_path может быть из converted/ или raw_videos/.
        """
        if video_path.exists():
            return video_path

        # Ищем по stem в raw_videos
        stem = video_path.stem
        for f in RAW_VIDEOS_DIR.iterdir():
            if f.stem == stem:
                return f

        raise FileNotFoundError(f"Видео не найдено: {video_path} и не найдено в raw_videos/")

    def full_analysis(self, video_path: Path, progress_callback: Optional[Callable] = None) -> dict:
        from src.features import PoseFeatureExtractor
        from web.backend.models.schemas import AnalysisStatus

        # Находим реальный путь
        video_path = self._find_video_path(video_path)

        def update(status, pct, msg):
            if progress_callback:
                progress_callback(status, pct, msg)

        update(AnalysisStatus.extracting_features, 10, "Извлечение признаков позы...")

        extractor = PoseFeatureExtractor(use_person_filter=True)
        result = extractor.extract_full_video(video_path)

        if len(result) == 5:
            features, landmarks, fps, det_mask, filter_stats = result
        else:
            features, landmarks, fps, det_mask = result

        extractor.close()

        # MediaPipe использует OpenGL/EGL — после закрытия синхронизируем GPU,
        # чтобы PyTorch-инференс получил чистый CUDA-контекст
        import torch as _torch
        if _torch.cuda.is_available():
            _torch.cuda.synchronize()
            _torch.cuda.empty_cache()

        video_id = video_path.stem

        np.save(str(CACHE_DIR / f"{video_id}_features.npy"), features)

        landmarks_serializable = []
        for lm in landmarks:
            if lm is None:
                landmarks_serializable.append(None)
            else:
                lm_dict = {}
                for name, values in lm.items():
                    lm_dict[name] = [round(float(v), 5) for v in values]
                landmarks_serializable.append(lm_dict)

        with open(CACHE_DIR / f"{video_id}_landmarks.json", "w") as f:
            json.dump(landmarks_serializable, f)

        update(AnalysisStatus.extracting_features, 30, "Признаки извлечены")
        update(AnalysisStatus.detecting_phases, 40, "Детекция фаз ударов...")

        if self._phase_trainer is None:
            raise RuntimeError("Детектор фаз не загружен")

        phases, phase_probs = self._phase_trainer.predict_video(features)
        strokes_raw = self._phase_trainer.extract_strokes(phases, fps)

        update(AnalysisStatus.detecting_phases, 55, f"Найдено {len(strokes_raw)} ударов")
        update(AnalysisStatus.classifying, 60, "Классификация типов ударов...")

        strokes_result = []
        for i, s in enumerate(strokes_raw):
            seg = features[s['start_frame']:s['end_frame'] + 1]
            if len(seg) < 3:
                continue

            if self._clf_trainer:
                pred_type, type_probs = self._clf_trainer.predict(seg)
                type_probs_dict = {
                    ml_config.IDX_TO_TYPE[j]: round(float(p), 4)
                    for j, p in enumerate(type_probs)
                }
            else:
                pred_type = "other"
                type_probs_dict = {}

            pct = 60 + (i / max(len(strokes_raw), 1)) * 20
            update(AnalysisStatus.classifying, pct, f"Удар {i+1}/{len(strokes_raw)}: {pred_type}")

            if self._error_trainer:
                type_idx = ml_config.TYPE_TO_IDX.get(pred_type, 6)
                errors, quality, error_probs = self._error_trainer.predict(seg, stroke_type=type_idx)
                error_probs_dict = {k: round(v, 4) for k, v in error_probs.items()}
            else:
                errors = []
                quality = 5.0
                error_probs_dict = {}

            strokes_result.append({
                "id": s["id"],
                "start_frame": s["start_frame"],
                "contact_frame": s["contact_frame"],
                "end_frame": s["end_frame"],
                "start_time": s["start_time"],
                "contact_time": s["contact_time"],
                "end_time": s["end_time"],
                "predicted_type": pred_type,
                "type_probabilities": type_probs_dict,
                "errors": errors,
                "error_probabilities": error_probs_dict,
                "quality": round(quality, 1),
            })

        update(AnalysisStatus.detecting_errors, 90, "Завершение...")

        return {
            "fps": round(fps, 2),
            "total_frames": len(features),
            "phases": [int(p) for p in phases],
            "phase_probs": [[round(float(v), 4) for v in row] for row in phase_probs],
            "strokes": strokes_result,
            "features_shape": list(features.shape),
            "detection_rate": round(float(np.mean(det_mask)) * 100, 1),
        }

    def save_auto_annotation(self, video_id: str, analysis_result: dict):
        annotation = {
            "video_id": video_id,
            "video": f"{video_id}.mp4",
            "fps": analysis_result["fps"],
            "frames": analysis_result["total_frames"],
            "duration": round(analysis_result["total_frames"] / analysis_result["fps"], 2),
            "auto_detected": True,
            "strokes": [],
        }

        for s in analysis_result["strokes"]:
            annotation["strokes"].append({
                "id": s["id"],
                "start_frame": s["start_frame"],
                "contact_frame": s["contact_frame"],
                "end_frame": s["end_frame"],
                "start_time": s["start_time"],
                "contact_time": s["contact_time"],
                "end_time": s["end_time"],
                "type": s["predicted_type"],
                "type_confidence": max(s["type_probabilities"].values()) if s["type_probabilities"] else 0,
                "quality": int(round(s["quality"])),
                "errors": s["errors"],
                "auto_detected": True,
            })

        path = ANNOTATIONS_DIR / f"{video_id}_auto.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(annotation, f, indent=2, ensure_ascii=False)

    def compute_attention(self, video_id: str, stroke: dict) -> dict:
        import torch

        features_path = CACHE_DIR / f"{video_id}_features.npy"
        if not features_path.exists():
            return {"error": "Признаки не найдены"}

        features = np.load(str(features_path))
        start = stroke["start_frame"]
        end = min(stroke["end_frame"] + 1, len(features))
        seg = features[start:end]

        if len(seg) < 3:
            return {"error": "Сегмент слишком короткий"}

        from src.data.preprocessing import normalize_sequence

        result = {
            "stroke_id": stroke["id"],
            "start_frame": start,
            "end_frame": end - 1,
            "n_frames": len(seg),
        }

        if self._clf_trainer and self._clf_trainer.model:
            tl = self._clf_trainer.cfg['target_length']
            feat_norm = normalize_sequence(seg, tl)
            x = torch.FloatTensor(feat_norm).unsqueeze(0).to(self._clf_trainer.device)

            with torch.no_grad():
                attn_weights = torch.softmax(self._clf_trainer.model.attention(x), dim=1)
                temporal = attn_weights.squeeze(-1).cpu().numpy()[0]

            from scipy.interpolate import interp1d
            if len(temporal) != len(seg):
                interp_fn = interp1d(np.linspace(0, 1, len(temporal)), temporal, kind='linear')
                temporal = interp_fn(np.linspace(0, 1, len(seg)))

            result["temporal_attention"] = [round(float(v), 4) for v in temporal]

            feature_importance = self._compute_feature_importance(self._clf_trainer, seg, tl)
            result["feature_importance"] = feature_importance

        if self._error_trainer and self._error_trainer.model:
            pred_type = stroke.get("predicted_type", "other")
            type_idx = ml_config.TYPE_TO_IDX.get(pred_type, 6)

            tl = self._error_trainer.cfg['target_length']
            feat_norm = normalize_sequence(seg, tl)
            feat_norm = np.nan_to_num(feat_norm, nan=0.0, posinf=5.0, neginf=-5.0)

            dev = self._error_trainer.device
            x = torch.FloatTensor(feat_norm).unsqueeze(0).to(dev)
            type_tensor = torch.LongTensor([type_idx]).to(dev)

            type_one_hot = torch.nn.functional.one_hot(
                type_tensor, num_classes=ml_config.NUM_TYPES
            ).float().unsqueeze(1).expand(-1, x.size(1), -1)
            x_combined = torch.cat([x, type_one_hot], dim=-1)

            with torch.no_grad():
                attn_weights = torch.softmax(self._error_trainer.model.attention(x_combined), dim=1)
                error_temporal = attn_weights.squeeze(-1).cpu().numpy()[0]

            from scipy.interpolate import interp1d
            if len(error_temporal) != len(seg):
                interp_fn = interp1d(np.linspace(0, 1, len(error_temporal)), error_temporal, kind='linear')
                error_temporal = interp_fn(np.linspace(0, 1, len(seg)))

            result["error_temporal_attention"] = [round(float(v), 4) for v in error_temporal]

            # Gradient-based saliency per detected error.
            # cuDNN LSTM backward is only supported in training mode, so we
            # disable cuDNN for this block (falls back to a slower but
            # gradient-compatible implementation) without touching model state.
            detected_errors = stroke.get("errors", [])
            if detected_errors:
                from scipy.interpolate import interp1d as _interp1d
                error_feature_importance = {}
                error_saliency = {}

                with torch.backends.cudnn.flags(enabled=False):
                    x_grad = torch.FloatTensor(feat_norm).unsqueeze(0).to(dev)
                    x_grad.requires_grad_(True)
                    out = self._error_trainer.model(x_grad, stroke_type=type_tensor)
                    logits = out['errors'][0]  # [num_errors]

                    for i, err_name in enumerate(ml_config.ERROR_TYPES):
                        if err_name not in detected_errors:
                            continue
                        if x_grad.grad is not None:
                            x_grad.grad.zero_()
                        logits[i].backward(retain_graph=True)

                        grads_matrix = x_grad.grad[0].abs().cpu().numpy()  # [seq_len, n_features]

                        mean_grads = grads_matrix.mean(axis=0)
                        mean_norm = mean_grads / (mean_grads.sum() + 1e-8)
                        error_feature_importance[err_name] = {
                            ml_config.FEATURE_NAMES[j]: round(float(mean_norm[j]), 6)
                            for j in range(min(len(mean_norm), len(ml_config.FEATURE_NAMES)))
                        }

                        top_idx = np.argsort(mean_grads)[::-1][:5]
                        top_features = [
                            ml_config.FEATURE_NAMES[j] for j in top_idx
                            if j < len(ml_config.FEATURE_NAMES)
                        ]
                        frame_gradients = {}
                        for j in top_idx:
                            if j >= len(ml_config.FEATURE_NAMES):
                                continue
                            fg = grads_matrix[:, j]
                            fg = fg / (fg.max() + 1e-8)
                            if len(fg) != len(seg):
                                fn = _interp1d(np.linspace(0, 1, len(fg)), fg, kind='linear')
                                fg = fn(np.linspace(0, 1, len(seg)))
                            frame_gradients[ml_config.FEATURE_NAMES[j]] = [
                                round(float(v), 4) for v in fg
                            ]

                        error_saliency[err_name] = {
                            "top_features": top_features,
                            "frame_gradients": frame_gradients,
                        }

                result["error_feature_importance"] = error_feature_importance
                result["error_saliency"] = error_saliency

        return result

    def _compute_feature_importance(self, trainer, seg, target_length) -> dict:
        import torch
        from src.data.preprocessing import normalize_sequence

        feat_norm = normalize_sequence(seg, target_length)
        feat_norm = np.nan_to_num(feat_norm, nan=0.0, posinf=5.0, neginf=-5.0)

        with torch.backends.cudnn.flags(enabled=False):
            x = torch.FloatTensor(feat_norm).unsqueeze(0).to(trainer.device)
            x.requires_grad_(True)
            logits = trainer.model(x)
            pred_class = logits.argmax(dim=-1)
            score = logits[0, pred_class]
            score.backward()

        grads = x.grad.abs().mean(dim=1).cpu().numpy()[0]
        grads = grads / (grads.sum() + 1e-8)

        importance = {}
        for i, name in enumerate(ml_config.FEATURE_NAMES):
            if i < len(grads):
                importance[name] = round(float(grads[i]), 6)

        return importance