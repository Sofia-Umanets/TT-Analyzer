"""
конфигурационный файл проекта
"""

from pathlib import Path


# ============================================================================
# ПУТИ
# ============================================================================

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_VIDEOS_DIR = DATA_DIR / "raw_videos"
ANNOTATIONS_DIR = DATA_DIR / "annotations"
CACHE_DIR = DATA_DIR / "cache"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Создаём папки при импорте
for d in [RAW_VIDEOS_DIR, ANNOTATIONS_DIR, CACHE_DIR, MODELS_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Файлы моделей
PHASE_MODEL_PATH = MODELS_DIR / "phase_detector.pth"
CLASSIFIER_MODEL_PATH = MODELS_DIR / "stroke_classifier.pth"
ERROR_MODEL_PATH = MODELS_DIR / "error_detector.pth"

# Кэш
FEATURES_CACHE_PATH = CACHE_DIR / "features_cache.pkl"


# ============================================================================
# ТИПЫ УДАРОВ
# ============================================================================

STROKE_TYPES = [
    'drive_forehand',      # 0
    'topspin_forehand',    # 1
    'slice_forehand',      # 2
    'drive_backhand',      # 3
    'topspin_backhand',    # 4
    'slice_backhand',      # 5
    'other',               # 6
]

TYPE_TO_IDX = {name: i for i, name in enumerate(STROKE_TYPES)}
IDX_TO_TYPE = {i: name for i, name in enumerate(STROKE_TYPES)}
NUM_TYPES = len(STROKE_TYPES)

# Человекочитаемые названия
TYPE_DISPLAY_NAMES = {
    'drive_forehand': 'Drive FH',
    'topspin_forehand': 'Topspin FH',
    'slice_forehand': 'Slice FH',
    'drive_backhand': 'Drive BH',
    'topspin_backhand': 'Topspin BH',
    'slice_backhand': 'Slice BH',
    'other': 'Other',
}


# ============================================================================
# ТИПЫ ОШИБОК
# ============================================================================

ERROR_TYPES = [
    'arm_far',            # Рука далеко от корпуса
    'big_swing',          # Слишком большой замах
    'left_hand_up',       # Поднята левая рука (за корпусом)
    'low_backswing',      # Замах снизу
    'low_elbow_end',      # Локоть низко в конце
    'no_forearm',         # Нет работы предплечья
    'no_rotation',        # Нет вращения корпуса
    'raised_elbow',       # Поднят локоть
    'raised_shoulder',    # Поднято плечо
    'sideways_finish',    # Концовка вбок
    'straight_arm',       # Прямая рука в конце
    'straight_body',      # Прямой корпус
    'straight_legs',      # Прямые ноги
    'straight_line',      # Движение по прямой
    'wrist_bent_back',    # Кисть выгнута назад
    'wrist_bent_fwd',     # Кисть согнута вперёд
    'wrist_up',           # Кисть вверх в конце
    'incomplete_follow_through',    # не доводит движение до конца
    'left_hand_behind_body',   #левая рука поднята
    'vertical_swing',   #движение снизу вверх (неправильная амплитуда)
]

ERROR_TO_IDX = {name: i for i, name in enumerate(ERROR_TYPES)}
IDX_TO_ERROR = {i: name for i, name in enumerate(ERROR_TYPES)}
NUM_ERRORS = len(ERROR_TYPES)


# ============================================================================
# ФАЗЫ УДАРА
# ============================================================================

PHASE_NAMES = ['idle', 'backswing', 'contact', 'follow_through']
NUM_PHASES = len(PHASE_NAMES)
CONTACT_WINDOW = 2  # ±2 кадра вокруг contact_frame


# ============================================================================
# ПРИЗНАКИ
# ============================================================================

NUM_FEATURES = 62  # Количество признаков на кадр

# Группы признаков (для анализа важности)
FEATURE_GROUPS = {
    'joint_angles': (0, 12),
    'relative_positions': (12, 24),
    'body_stance': (24, 34),
    'velocities_accelerations': (34, 46),
    'phase_features': (46, 54),
    'symmetry_balance': (54, 62),
}

FEATURE_NAMES = [
    # Углы [0:12]
    'right_elbow_angle', 'left_elbow_angle',
    'right_shoulder_angle', 'left_shoulder_angle',
    'right_knee_angle', 'left_knee_angle',
    'right_hip_angle', 'left_hip_angle',
    'right_wrist_index_angle', 'left_wrist_index_angle',
    'right_wrist_pinky_angle', 'left_wrist_pinky_angle',
    # Относительные позиции [12:24]
    'right_wrist_rel_x', 'right_wrist_rel_y', 'right_wrist_rel_z',
    'left_wrist_rel_x', 'left_wrist_rel_y', 'left_wrist_rel_z',
    'right_elbow_rel_x', 'right_elbow_rel_y', 'right_elbow_rel_z',
    'left_elbow_rel_x', 'left_elbow_rel_y', 'left_elbow_rel_z',
    # Корпус и стойка [24:34]
    'shoulder_hip_rotation', 'torso_forward_tilt', 'torso_side_tilt',
    'shoulder_height_diff', 'stance_width', 'hip_height_ratio',
    'center_gravity_shift', 'right_wrist_dist_body',
    'left_wrist_dist_body', 'right_elbow_height_vs_shoulder',
    # Скорости и ускорения [34:46]
    'right_wrist_speed', 'left_wrist_speed',
    'right_elbow_speed', 'left_elbow_speed',
    'right_shoulder_speed', 'left_shoulder_speed',
    'right_hip_speed', 'left_hip_speed',
    'right_wrist_accel', 'left_wrist_accel',
    'right_elbow_angular_vel', 'right_shoulder_angular_vel',
    # Фазовые [46:54]
    'right_wrist_dir_x', 'right_wrist_dir_y', 'right_wrist_dir_z',
    'left_wrist_dir_x', 'left_wrist_dir_y', 'left_wrist_dir_z',
    'right_wrist_from_neutral', 'left_wrist_from_neutral',
    # Симметрия [54:62]
    'elbow_angle_diff', 'shoulder_angle_diff',
    'knee_angle_diff', 'wrist_distance',
    'right_wrist_height_vs_shoulder', 'left_wrist_height_vs_shoulder',
    'right_wrist_visibility', 'left_wrist_visibility',
]


# ============================================================================
# ГИПЕРПАРАМЕТРЫ МОДЕЛЕЙ
# ============================================================================

# Детектор фаз (LSTM)
PHASE_DETECTOR = {
    'hidden_size': 128,
    'num_layers': 2,
    'seq_length': 64,
    'overlap': 32,
    'epochs': 40,
    'batch_size': 16,
    'lr': 0.001,
    'min_stroke_frames': 5,
}

# Классификатор типов
STROKE_CLASSIFIER = {
    'hidden_size': 128,
    'num_layers': 2,
    'target_length': 30,  # Нормализованная длина последовательности
    'epochs': 60,
    'batch_size': 16,
    'lr': 0.001,
}

# Детектор ошибок
ERROR_DETECTOR = {
    'hidden_size': 128,
    'num_layers': 2,
    'target_length': 30,
    'epochs': 80,
    'batch_size': 16,
    'lr': 0.0005,
    'error_threshold': 0.5,
}


# ============================================================================
# MEDIAPIPE
# ============================================================================

MEDIAPIPE = {
    'model_complexity': 2,
    'min_detection_confidence': 0.5,
    'min_tracking_confidence': 0.5,
}

LANDMARKS = {
    'nose': 0,
    'left_eye': 2, 'right_eye': 5,
    'left_ear': 7, 'right_ear': 8,
    'left_shoulder': 11, 'right_shoulder': 12,
    'left_elbow': 13, 'right_elbow': 14,
    'left_wrist': 15, 'right_wrist': 16,
    'left_pinky': 17, 'right_pinky': 18,
    'left_index': 19, 'right_index': 20,
    'left_thumb': 21, 'right_thumb': 22,
    'left_hip': 23, 'right_hip': 24,
    'left_knee': 25, 'right_knee': 26,
    'left_ankle': 27, 'right_ankle': 28,
    'left_heel': 29, 'right_heel': 30,
    'left_foot_index': 31, 'right_foot_index': 32,
}


# ============================================================================
# ФИЛЬТРАЦИЯ ЦЕЛЕВОГО ИГРОКА
# ============================================================================

PERSON_FILTER = {
    'enabled': True,                # Включить фильтрацию
    'min_completeness': 0.6,        # Мин. доля видимых essential landmarks
    'max_center_shift': 0.15,       # Макс. смещение центра между кадрами
    'min_bbox_area': 0.02,          # Мин. площадь bbox (доля от кадра)
    'crop_padding': 0.2,            # Запас при кропе
    'use_crop_recovery': True,      # Использовать кроп для восстановления
    'max_lost_frames': 10,          # Макс. кадров без детекции до сброса
    'save_debug_video': False,      # Сохранять debug видео
}

# Ключевые landmarks, которые должны быть видны у целевого игрока
ESSENTIAL_LANDMARKS_INDICES = [11, 12, 13, 14, 15, 16, 23, 24]