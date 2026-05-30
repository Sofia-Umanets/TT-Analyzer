"""
Фильтрация целевого игрока в кадре.

Стратегия:
  1. Детектируем всех людей в кадре (MediaPipe Pose или Holistic)
  2. Выбираем "главного" — самый крупный bounding box (ближе к камере)
  3. Проверяем целостность скелета (видимость ключевых точек)
  4. Трекинг: если на предыдущем кадре уже был выбран человек,
     предпочитаем того, чей центр ближе к предыдущему (IoU / расстояние)
  5. Кропаем кадр с запасом и отдаём в PoseFeatureExtractor

Это защищает от:
  - Переключения MediaPipe между людьми
  - Ложных срабатываний на фоновых людей
  - Промелькивающих рук/плеч другого человека
"""

import numpy as np
import cv2
import mediapipe as mp
from dataclasses import dataclass, field
from typing import Optional, Tuple, List


@dataclass
class PersonBBox:
    """Bounding box человека в нормализованных координатах [0,1]."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    area: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    completeness: float = 0.0  # Доля видимых ключевых точек
    landmarks: object = None    # Оригинальные landmarks MediaPipe

    def __post_init__(self):
        self.area = (self.x_max - self.x_min) * (self.y_max - self.y_min)
        self.center_x = (self.x_min + self.x_max) / 2
        self.center_y = (self.y_min + self.y_max) / 2


# Ключевые точки, которые ДОЛЖНЫ быть видны у целевого игрока
# (плечи, локти, запястья, бёдра — минимум для анализа удара)
ESSENTIAL_LANDMARKS = [11, 12, 13, 14, 15, 16, 23, 24]  # shoulders, elbows, wrists, hips
UPPER_BODY_LANDMARKS = list(range(0, 25))  # Все точки верхней части тела

# Минимальная видимость для "хорошей" точки
VISIBILITY_THRESHOLD = 0.5

# Минимальная доля видимых essential landmarks для "целостного" человека
MIN_COMPLETENESS = 0.6

# Максимальное смещение центра между кадрами (в долях от размера кадра)
MAX_CENTER_SHIFT = 0.15

# Минимальная площадь bbox (в долях от площади кадра) — отсекаем мелких людей на фоне
MIN_BBOX_AREA = 0.02

# Запас при кропе (в долях от размера bbox)
CROP_PADDING = 0.2


class PersonFilter:
    """
    Выбирает целевого игрока из кадра и возвращает его landmarks.
    
    Использует mp.solutions.pose в режиме multi-person detection:
    сначала находим всех кандидатов, потом выбираем лучшего.
    """

    def __init__(self, 
                 min_completeness: float = MIN_COMPLETENESS,
                 max_center_shift: float = MAX_CENTER_SHIFT,
                 min_bbox_area: float = MIN_BBOX_AREA,
                 crop_padding: float = CROP_PADDING,
                 use_crop: bool = True):
        """
        Parameters
        ----------
        min_completeness : float
            Минимальная доля видимых essential landmarks
        max_center_shift : float  
            Макс. смещение центра между кадрами (для трекинга)
        min_bbox_area : float
            Минимальная площадь bbox (отсечение фоновых людей)
        crop_padding : float
            Запас при кропе вокруг выбранного человека
        use_crop : bool
            Если True, кропаем кадр вокруг выбранного человека
            перед финальной обработкой (повышает точность)
        """
        self.min_completeness = min_completeness
        self.max_center_shift = max_center_shift
        self.min_bbox_area = min_bbox_area
        self.crop_padding = crop_padding
        self.use_crop = use_crop

        # Состояние трекинга
        self._prev_bbox: Optional[PersonBBox] = None
        self._lost_frames: int = 0
        self._max_lost_frames: int = 10  # После стольких потерь — сброс трекинга

        self._mp_pose = mp.solutions.pose
        self._detector = None
        self._main_pose = None

    def init(self, model_complexity=2, 
             min_detection_confidence=0.5,
             min_tracking_confidence=0.5):
        """Инициализирует MediaPipe модели."""
        self._main_pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            enable_segmentation=False,
        )
        
        self._static_pose = self._mp_pose.Pose(
            static_image_mode=True,
            model_complexity=1,  # Быстрее для детекции
            min_detection_confidence=min_detection_confidence,
        )
        
        self.reset()

    def reset(self):
        """Сбрасывает состояние трекинга (для нового видео)."""
        self._prev_bbox = None
        self._lost_frames = 0

    def close(self):
        """Освобождает ресурсы."""
        if self._main_pose:
            self._main_pose.close()
            self._main_pose = None
        if self._static_pose:
            self._static_pose.close()
            self._static_pose = None

    # ------------------------------------------------------------------
    # Основной метод
    # ------------------------------------------------------------------

    def process_frame(self, frame_bgr) -> Tuple[Optional[object], Optional[PersonBBox], dict]:
        """
        Обрабатывает один кадр и возвращает landmarks целевого игрока.

        Parameters
        ----------
        frame_bgr : np.ndarray
            Кадр в формате BGR (из cv2)

        Returns
        -------
        landmarks : MediaPipe pose_landmarks или None
            Landmarks выбранного игрока (в координатах ПОЛНОГО кадра)
        bbox : PersonBBox или None
            Bounding box выбранного игрока
        debug_info : dict
            Отладочная информация
        """
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        debug = {
            'n_candidates': 0,
            'selected': False,
            'method': 'none',
            'crop_used': False,
        }

        # Шаг 1: Получаем landmarks от основного трекера
        result = self._main_pose.process(rgb)

        if result.pose_landmarks is None:
            # Трекер потерял человека
            self._lost_frames += 1
            debug['method'] = 'lost'

            if self._lost_frames > self._max_lost_frames:
                self.reset()

            return None, None, debug

        # Шаг 2: Проверяем, что найденный человек — наш целевой
        bbox = self._landmarks_to_bbox(result.pose_landmarks)
        
        is_valid = self._validate_person(bbox, result.pose_landmarks)
        is_tracked = self._check_tracking(bbox)

        if is_valid and is_tracked:
            # Всё хорошо — это наш игрок
            self._prev_bbox = bbox
            self._lost_frames = 0
            bbox.landmarks = result.pose_landmarks
            debug['selected'] = True
            debug['method'] = 'tracking'
            return result.pose_landmarks, bbox, debug

        # Шаг 3: Если валидация не прошла — возможно, MediaPipe 
        # переключился на другого человека. Пробуем кроп.
        if self._prev_bbox is not None and self.use_crop:
            cropped_result = self._try_crop_detection(rgb, self._prev_bbox, w, h)
            if cropped_result is not None:
                landmarks, crop_bbox = cropped_result
                self._prev_bbox = crop_bbox
                self._lost_frames = 0
                crop_bbox.landmarks = landmarks
                debug['selected'] = True
                debug['method'] = 'crop_recovery'
                debug['crop_used'] = True
                return landmarks, crop_bbox, debug

        # Шаг 4: Если это первый кадр или трекинг потерян — 
        # выбираем самого крупного/целостного человека
        if self._prev_bbox is None or self._lost_frames > 3:
            best = self._select_best_person(result.pose_landmarks, bbox)
            if best is not None:
                self._prev_bbox = best
                self._lost_frames = 0
                debug['selected'] = True
                debug['method'] = 'initial_selection'
                return best.landmarks, best, debug

        # Ничего не нашли
        self._lost_frames += 1
        debug['method'] = 'failed'
        return None, None, debug

    # ------------------------------------------------------------------
    # Валидация и выбор
    # ------------------------------------------------------------------

    def _landmarks_to_bbox(self, pose_landmarks) -> PersonBBox:
        """Вычисляет bounding box и метрики из landmarks."""
        xs, ys, vis = [], [], []
        for lm in pose_landmarks.landmark:
            xs.append(lm.x)
            ys.append(lm.y)
            vis.append(lm.visibility)

        # Считаем completeness по essential landmarks
        essential_visible = sum(
            1 for idx in ESSENTIAL_LANDMARKS
            if pose_landmarks.landmark[idx].visibility > VISIBILITY_THRESHOLD
        )
        completeness = essential_visible / len(ESSENTIAL_LANDMARKS)

        # bbox с небольшим запасом
        margin = 0.02
        bbox = PersonBBox(
            x_min=max(0, min(xs) - margin),
            y_min=max(0, min(ys) - margin),
            x_max=min(1, max(xs) + margin),
            y_max=min(1, max(ys) + margin),
            completeness=completeness,
        )
        return bbox

    def _validate_person(self, bbox: PersonBBox, landmarks) -> bool:
        """
        Проверяет, что обнаруженный человек — целевой игрок.
        
        Критерии:
        1. Достаточная площадь bbox (не фоновый человек)
        2. Достаточная целостность скелета (не рука/плечо)
        3. Видны essential landmarks
        """
        # Слишком маленький — фоновый человек
        if bbox.area < self.min_bbox_area:
            return False

        # Недостаточно видимых ключевых точек — это не целый человек
        if bbox.completeness < self.min_completeness:
            return False

        # Проверяем, что видны ОБА плеча (иначе это может быть чужая рука)
        l_shoulder_vis = landmarks.landmark[11].visibility
        r_shoulder_vis = landmarks.landmark[12].visibility
        if l_shoulder_vis < VISIBILITY_THRESHOLD and r_shoulder_vis < VISIBILITY_THRESHOLD:
            return False

        return True

    def _check_tracking(self, bbox: PersonBBox) -> bool:
        """
        Проверяет, что текущий bbox соответствует предыдущему 
        (тот же человек, не переключение).
        """
        if self._prev_bbox is None:
            return True  # Первый кадр — принимаем

        # Расстояние между центрами
        dx = abs(bbox.center_x - self._prev_bbox.center_x)
        dy = abs(bbox.center_y - self._prev_bbox.center_y)
        shift = np.sqrt(dx**2 + dy**2)

        if shift > self.max_center_shift:
            return False  # Слишком далеко — скорее всего другой человек

        # Проверяем, что размер не изменился резко (±50%)
        area_ratio = bbox.area / (self._prev_bbox.area + 1e-8)
        if area_ratio < 0.5 or area_ratio > 2.0:
            return False

        return True

    def _select_best_person(self, pose_landmarks, bbox: PersonBBox) -> Optional[PersonBBox]:
        """
        Выбирает лучшего кандидата (для первого кадра или после потери).
        
        Сейчас MediaPipe Pose возвращает только одного человека,
        поэтому просто валидируем его. Если нужно — можно расширить
        через MediaPipe Holistic или внешний детектор.
        """
        if self._validate_person(bbox, pose_landmarks):
            bbox.landmarks = pose_landmarks
            return bbox
        return None

    def _try_crop_detection(self, rgb, prev_bbox: PersonBBox, 
                            w: int, h: int) -> Optional[Tuple]:
        """
        Пробует найти человека в кропе вокруг предыдущего положения.
        Это помогает, когда MediaPipe переключился на другого человека.
        """
        pad = self.crop_padding

        # Координаты кропа в пикселях
        x1 = max(0, int((prev_bbox.x_min - pad) * w))
        y1 = max(0, int((prev_bbox.y_min - pad) * h))
        x2 = min(w, int((prev_bbox.x_max + pad) * w))
        y2 = min(h, int((prev_bbox.y_max + pad) * h))

        if x2 - x1 < 50 or y2 - y1 < 50:
            return None

        crop = rgb[y1:y2, x1:x2]
        result = self._static_pose.process(crop)

        if result.pose_landmarks is None:
            return None

        # Пересчитываем координаты из кропа в полный кадр
        crop_w = x2 - x1
        crop_h = y2 - y1

        for lm in result.pose_landmarks.landmark:
            lm.x = (lm.x * crop_w + x1) / w
            lm.y = (lm.y * crop_h + y1) / h
            # z оставляем как есть (относительная глубина)

        bbox = self._landmarks_to_bbox(result.pose_landmarks)

        if self._validate_person(bbox, result.pose_landmarks):
            return result.pose_landmarks, bbox

        return None

    # ------------------------------------------------------------------
    # Утилиты для отладки
    # ------------------------------------------------------------------

    def draw_debug(self, frame_bgr, bbox: Optional[PersonBBox], 
                   debug_info: dict) -> np.ndarray:
        """Рисует отладочную информацию на кадре."""
        vis = frame_bgr.copy()
        h, w = vis.shape[:2]

        if bbox is not None:
            # Зелёный прямоугольник вокруг выбранного человека
            x1 = int(bbox.x_min * w)
            y1 = int(bbox.y_min * h)
            x2 = int(bbox.x_max * w)
            y2 = int(bbox.y_max * h)
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Информация
            info_text = f"{debug_info['method']} | comp={bbox.completeness:.2f}"
            cv2.putText(vis, info_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            cv2.putText(vis, f"LOST ({debug_info['method']})", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return vis