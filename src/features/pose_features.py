"""
Извлечение 62 признаков из видео с помощью MediaPipe Pose.
С фильтрацией целевого игрока (PersonFilter).

Группы признаков:
  [0:12]  — углы суставов
  [12:24] — относительные позиции
  [24:34] — корпус и стойка
  [34:46] — скорости и ускорения
  [46:54] — фазовые признаки
  [54:62] — симметрия и баланс
"""

import numpy as np
import cv2
import mediapipe as mp

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from src.features.person_filter import PersonFilter


class PoseFeatureExtractor:
    """Извлекает 62 признака из каждого кадра видео с фильтрацией игрока."""

    def __init__(self, use_person_filter=True):
        """
        Parameters
        ----------
        use_person_filter : bool
            Если True — используется PersonFilter для выбора целевого игрока.
            Если False — стандартное поведение MediaPipe (один человек).
        """
        self._mp_pose = mp.solutions.pose
        self._pose = None
        self._prev = None
        self._prev_prev = None
        
        # Фильтр целевого игрока
        self._use_filter = use_person_filter
        self._person_filter = PersonFilter() if use_person_filter else None

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def extract_full_video(self, video_path, save_debug_video=False):
        """
        Извлекает признаки из всего видео.

        Parameters
        ----------
        video_path : str or Path
        save_debug_video : bool
            Если True — сохраняет видео с визуализацией выбора игрока

        Returns
        -------
        features : np.ndarray, shape (N, 62)
        landmarks_list : list[dict | None]
        fps : float
        detection_mask : np.ndarray, shape (N,), dtype bool
        filter_stats : dict  (статистика фильтрации)
        """
        self._init()
        self._reset()

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Debug video writer
        debug_writer = None
        if save_debug_video and self._use_filter:
            debug_path = str(video_path).rsplit('.', 1)[0] + '_debug_filter.mp4'
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            debug_writer = cv2.VideoWriter(debug_path, fourcc, fps, (frame_w, frame_h))

        features_list = []
        landmarks_list = []
        detection_mask = []
        
        # Статистика фильтрации
        filter_stats = {
            'total_frames': 0,
            'detected': 0,
            'tracking': 0,
            'crop_recovery': 0,
            'initial_selection': 0,
            'lost': 0,
            'failed': 0,
        }

        for idx in range(total):
            ret, frame = cap.read()
            if not ret:
                break

            filter_stats['total_frames'] += 1
            
            if self._use_filter:
                pose_landmarks, bbox, debug_info = self._person_filter.process_frame(frame)
                
                # Обновляем статистику
                method = debug_info.get('method', 'none')
                if method in filter_stats:
                    filter_stats[method] += 1
                if debug_info.get('selected', False):
                    filter_stats['detected'] += 1

                # Debug видео
                if debug_writer is not None:
                    debug_frame = self._person_filter.draw_debug(frame, bbox, debug_info)
                    debug_writer.write(debug_frame)

                if pose_landmarks is not None:
                    lm = self._parse_landmarks(pose_landmarks)
                    feat = self._compute(lm, fps)
                    features_list.append(feat)
                    landmarks_list.append(lm)
                    detection_mask.append(True)
                    self._prev_prev = self._prev
                    self._prev = lm
                else:
                    self._append_fallback(features_list, landmarks_list, detection_mask)
            else:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self._pose.process(rgb)

                if result.pose_landmarks:
                    lm = self._parse_landmarks(result.pose_landmarks)
                    feat = self._compute(lm, fps)
                    features_list.append(feat)
                    landmarks_list.append(lm)
                    detection_mask.append(True)
                    self._prev_prev = self._prev
                    self._prev = lm
                else:
                    self._append_fallback(features_list, landmarks_list, detection_mask)

            if idx % 200 == 0:
                pct = idx / total * 100
                print(f"    Кадр {idx}/{total} ({pct:.0f}%)", end="\r")

        cap.release()
        if debug_writer:
            debug_writer.release()
            print(f"    Debug видео: {debug_path}")

        det_rate = np.mean(detection_mask) * 100
        print(f"    Извлечено {len(features_list)} кадров, детекция: {det_rate:.1f}%")
        
        if self._use_filter:
            print(f"    Фильтрация: tracking={filter_stats['tracking']}, "
                  f"crop_recovery={filter_stats['crop_recovery']}, "
                  f"lost={filter_stats['lost']}, failed={filter_stats['failed']}")

        return (np.array(features_list),
                landmarks_list,
                fps,
                np.array(detection_mask),
                filter_stats)

    def extract_segment(self, video_path, start_frame, end_frame):
        """Извлекает признаки из сегмента [start_frame, end_frame]."""
        self._init()
        self._reset()

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        # Для фильтра нужно "прогреть" трекинг за несколько кадров до start
        warmup = 15 if self._use_filter else 0
        actual_start = max(0, start_frame - warmup)
        cap.set(cv2.CAP_PROP_POS_FRAMES, actual_start)

        features_list = []
        current_frame = actual_start
        
        for _ in range(actual_start, end_frame + 1):
            ret, frame = cap.read()
            if not ret:
                break

            if self._use_filter:
                pose_landmarks, bbox, debug_info = self._person_filter.process_frame(frame)
                
                if current_frame >= start_frame:
                    if pose_landmarks is not None:
                        lm = self._parse_landmarks(pose_landmarks)
                        feat = self._compute(lm, fps)
                        features_list.append(feat)
                        self._prev_prev = self._prev
                        self._prev = lm
                    else:
                        if features_list:
                            features_list.append(features_list[-1].copy())
                        else:
                            features_list.append(np.zeros(config.NUM_FEATURES))
            else:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self._pose.process(rgb)

                if current_frame >= start_frame:
                    if result.pose_landmarks:
                        lm = self._parse_landmarks(result.pose_landmarks)
                        feat = self._compute(lm, fps)
                        features_list.append(feat)
                        self._prev_prev = self._prev
                        self._prev = lm
                    else:
                        if features_list:
                            features_list.append(features_list[-1].copy())
                        else:
                            features_list.append(np.zeros(config.NUM_FEATURES))

            current_frame += 1

        cap.release()
        return np.array(features_list), fps

    def close(self):
        if self._pose:
            self._pose.close()
            self._pose = None
        if self._person_filter:
            self._person_filter.close()

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _init(self):
        if self._use_filter:
            self._person_filter.init(
                model_complexity=config.MEDIAPIPE['model_complexity'],
                min_detection_confidence=config.MEDIAPIPE['min_detection_confidence'],
                min_tracking_confidence=config.MEDIAPIPE['min_tracking_confidence'],
            )
        else:
            if self._pose is None:
                self._pose = self._mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=config.MEDIAPIPE['model_complexity'],
                    min_detection_confidence=config.MEDIAPIPE['min_detection_confidence'],
                    min_tracking_confidence=config.MEDIAPIPE['min_tracking_confidence'],
                )

    def _reset(self):
        self._prev = None
        self._prev_prev = None
        if self._person_filter:
            self._person_filter.reset()

    def _append_fallback(self, features_list, landmarks_list, detection_mask):
        """Добавляет fallback значения при отсутствии детекции."""
        if features_list:
            features_list.append(features_list[-1].copy())
            landmarks_list.append(landmarks_list[-1])
        else:
            features_list.append(np.zeros(config.NUM_FEATURES))
            landmarks_list.append(None)
        detection_mask.append(False)

    def _parse_landmarks(self, pose_landmarks):
        lm = {}
        for name, idx in config.LANDMARKS.items():
            p = pose_landmarks.landmark[idx]
            lm[name] = np.array([p.x, p.y, p.z, p.visibility])
        return lm

    # ---------- вспомогательные геометрические функции ----------

    @staticmethod
    def _pt(lm, name):
        return lm[name][:3]

    @staticmethod
    def _angle(a, b, c):
        """Угол в точке b."""
        v1, v2 = a - b, c - b
        cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        return np.degrees(np.arccos(np.clip(cos, -1, 1)))

    @staticmethod
    def _dist(a, b):
        return np.linalg.norm(a - b)

    # ---------- основной расчёт ----------

    def _compute(self, lm, fps):
        f = np.zeros(config.NUM_FEATURES)
        pt = lambda n: self._pt(lm, n)
        ang = self._angle
        dst = self._dist

        body_scale = dst(pt('right_shoulder'), pt('right_hip')) + 1e-8
        shoulder_c = (pt('right_shoulder') + pt('left_shoulder')) / 2
        hip_c = (pt('right_hip') + pt('left_hip')) / 2

        # --- УГЛЫ [0:12] ---
        f[0] = ang(pt('right_shoulder'), pt('right_elbow'), pt('right_wrist'))
        f[1] = ang(pt('left_shoulder'), pt('left_elbow'), pt('left_wrist'))
        f[2] = ang(pt('right_elbow'), pt('right_shoulder'), pt('right_hip'))
        f[3] = ang(pt('left_elbow'), pt('left_shoulder'), pt('left_hip'))
        f[4] = ang(pt('right_hip'), pt('right_knee'), pt('right_ankle'))
        f[5] = ang(pt('left_hip'), pt('left_knee'), pt('left_ankle'))
        f[6] = ang(pt('right_shoulder'), pt('right_hip'), pt('right_knee'))
        f[7] = ang(pt('left_shoulder'), pt('left_hip'), pt('left_knee'))
        f[8] = ang(pt('right_elbow'), pt('right_wrist'), pt('right_index'))
        f[9] = ang(pt('left_elbow'), pt('left_wrist'), pt('left_index'))
        f[10] = ang(pt('right_elbow'), pt('right_wrist'), pt('right_pinky'))
        f[11] = ang(pt('left_elbow'), pt('left_wrist'), pt('left_pinky'))

        # --- ОТНОСИТЕЛЬНЫЕ ПОЗИЦИИ [12:24] ---
        f[12:15] = (pt('right_wrist') - shoulder_c) / body_scale
        f[15:18] = (pt('left_wrist') - shoulder_c) / body_scale
        f[18:21] = (pt('right_elbow') - pt('right_shoulder')) / body_scale
        f[21:24] = (pt('left_elbow') - pt('left_shoulder')) / body_scale

        # --- КОРПУС И СТОЙКА [24:34] ---
        sh_vec = lm['right_shoulder'][:2] - lm['left_shoulder'][:2]
        hp_vec = lm['right_hip'][:2] - lm['left_hip'][:2]
        f[24] = np.degrees(
            np.arctan2(sh_vec[1], sh_vec[0]) - np.arctan2(hp_vec[1], hp_vec[0]))

        torso = shoulder_c - hip_c
        torso_n = torso / (np.linalg.norm(torso) + 1e-8)
        f[25] = np.degrees(np.arccos(np.clip(np.dot(torso_n, [0, -1, 0]), -1, 1)))
        f[26] = np.degrees(np.arccos(np.clip(np.dot(torso_n, [1, 0, 0]), -1, 1)))
        f[27] = (lm['right_shoulder'][1] - lm['left_shoulder'][1]) * 100

        hip_w = dst(lm['left_hip'][:2], lm['right_hip'][:2]) + 1e-8
        ankle_d = dst(lm['left_ankle'][:2], lm['right_ankle'][:2])
        f[28] = ankle_d / hip_w

        ankle_c = (pt('right_ankle') + pt('left_ankle')) / 2
        total_h = dst(shoulder_c[:2], ankle_c[:2]) + 1e-8
        f[29] = dst(hip_c[:2], ankle_c[:2]) / total_h
        f[30] = (hip_c[0] - ankle_c[0]) * 10
        f[31] = dst(pt('right_wrist'), shoulder_c) / body_scale
        f[32] = dst(pt('left_wrist'), shoulder_c) / body_scale
        f[33] = (pt('right_shoulder')[1] - pt('right_elbow')[1]) * 100

        # --- СКОРОСТИ И УСКОРЕНИЯ [34:46] ---
        dt = 1.0 / fps if fps > 0 else 1.0 / 30.0
        if self._prev is not None:
            pp = lambda n: self._pt(self._prev, n)
            f[34] = dst(pt('right_wrist'), pp('right_wrist')) / dt
            f[35] = dst(pt('left_wrist'), pp('left_wrist')) / dt
            f[36] = dst(pt('right_elbow'), pp('right_elbow')) / dt
            f[37] = dst(pt('left_elbow'), pp('left_elbow')) / dt
            f[38] = dst(pt('right_shoulder'), pp('right_shoulder')) / dt
            f[39] = dst(pt('left_shoulder'), pp('left_shoulder')) / dt
            f[40] = dst(pt('right_hip'), pp('right_hip')) / dt
            f[41] = dst(pt('left_hip'), pp('left_hip')) / dt

            if self._prev_prev is not None:
                ppp = lambda n: self._pt(self._prev_prev, n)
                prev_v_rw = dst(pp('right_wrist'), ppp('right_wrist')) / dt
                f[42] = (f[34] - prev_v_rw) / dt
                prev_v_lw = dst(pp('left_wrist'), ppp('left_wrist')) / dt
                f[43] = (f[35] - prev_v_lw) / dt

                prev_ea = ang(pp('right_shoulder'), pp('right_elbow'), pp('right_wrist'))
                f[44] = (f[0] - prev_ea) / dt
                prev_sa = ang(pp('right_elbow'), pp('right_shoulder'), pp('right_hip'))
                f[45] = (f[2] - prev_sa) / dt

        # --- ФАЗОВЫЕ [46:54] ---
        if self._prev is not None:
            pp = lambda n: self._pt(self._prev, n)
            rw_dir = pt('right_wrist') - pp('right_wrist')
            rw_dir_n = rw_dir / (np.linalg.norm(rw_dir) + 1e-8)
            f[46:49] = rw_dir_n

            lw_dir = pt('left_wrist') - pp('left_wrist')
            lw_dir_n = lw_dir / (np.linalg.norm(lw_dir) + 1e-8)
            f[49:52] = lw_dir_n

        neutral = shoulder_c + np.array([0, 0.3 * body_scale, 0])
        f[52] = dst(pt('right_wrist'), neutral) / body_scale
        f[53] = dst(pt('left_wrist'), neutral) / body_scale

        # --- СИММЕТРИЯ [54:62] ---
        f[54] = f[0] - f[1]
        f[55] = f[2] - f[3]
        f[56] = f[4] - f[5]
        f[57] = dst(pt('right_wrist'), pt('left_wrist')) / body_scale
        f[58] = (shoulder_c[1] - pt('right_wrist')[1]) * 100
        f[59] = (shoulder_c[1] - pt('left_wrist')[1]) * 100
        f[60] = lm['right_wrist'][3]
        f[61] = lm['left_wrist'][3]

        return f