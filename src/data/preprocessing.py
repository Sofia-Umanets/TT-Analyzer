"""
Подготовка данных: кэширование признаков, создание меток фаз,
нормализация последовательностей.
"""

import json
import pickle
import numpy as np
from pathlib import Path
from collections import Counter

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from src.features import PoseFeatureExtractor


def find_video(videos_dir, video_name):
    """Ищет видео файл, пробуя разные расширения."""
    p = Path(videos_dir) / video_name
    if p.exists():
        return p
    for ext in ('.mp4', '.MP4', '.mov', '.MOV', '.avi', '.AVI'):
        alt = Path(videos_dir) / (Path(video_name).stem + ext)
        if alt.exists():
            return alt
    return None


def create_phase_labels(total_frames, strokes):
    """
    Покадровая разметка фаз.

    0 = idle, 1 = backswing, 2 = contact, 3 = follow_through
    """
    labels = np.zeros(total_frames, dtype=np.int64)
    cw = config.CONTACT_WINDOW

    for s in strokes:
        start = s['start_frame']
        contact = s['contact_frame']
        end = s['end_frame']

        for f in range(max(0, start), min(contact, total_frames)):
            labels[f] = 1
        for f in range(max(0, contact - cw), min(contact + cw + 1, total_frames)):
            labels[f] = 2
        for f in range(min(contact + cw + 1, total_frames), min(end + 1, total_frames)):
            labels[f] = 3

    return labels


def normalize_sequence(features, target_length):
    """Интерполяция последовательности к фиксированной длине."""
    n = len(features)
    if n == 0:
        return np.zeros((target_length, features.shape[1]
                          if len(features.shape) > 1 else config.NUM_FEATURES))
    if n == target_length:
        return features

    old_idx = np.linspace(0, 1, n)
    new_idx = np.linspace(0, 1, target_length)

    if features.ndim == 1:
        features = features.reshape(-1, 1)

    out = np.zeros((target_length, features.shape[1]))
    for i in range(features.shape[1]):
        out[:, i] = np.interp(new_idx, old_idx, features[:, i])
    return out


def _rebuild_aggregated(per_video):
    """Пересобирает объединённые массивы из per_video."""
    if not per_video:
        return np.empty((0, config.NUM_FEATURES)), np.empty(0, dtype=np.int64)
    all_features = np.vstack([v['features'] for v in per_video])
    all_labels = np.concatenate([v['labels'] for v in per_video])
    return all_features, all_labels


def build_features_cache(force=False):
    """
    Извлекает признаки из всех видео и сохраняет кэш.
    При force=False обновляет кэш инкрементально: добавляет новые видео,
    удаляет записи для отсутствующих аннотаций.
    """
    cache_path = config.FEATURES_CACHE_PATH

    # Загружаем существующий кэш, если не force
    existing_cache = None
    if cache_path.exists() and not force:
        try:
            with open(cache_path, 'rb') as f:
                existing_cache = pickle.load(f)
            print(f"Загружен существующий кэш: {cache_path}")
        except Exception as e:
            print(f"Ошибка загрузки кэша: {e}, будет создан новый")
            existing_cache = None

    # Список актуальных JSON-аннотаций (без _auto)
    json_files = sorted(config.ANNOTATIONS_DIR.glob("*.json"))
    json_files = [f for f in json_files if '_auto' not in f.stem]
    current_names = {f.name for f in json_files}

    # Определяем изменения, если есть существующий кэш
    if existing_cache is not None:
        per_video = existing_cache.get('per_video', [])
        cached_names = {v['info']['json'] for v in per_video}
        new_names = current_names - cached_names
        removed_names = cached_names - current_names

        if not new_names and not removed_names:
            print(f"Кэш актуален, новых видео нет. Всего видео: {len(per_video)}")
            return existing_cache

        # Удаляем устаревшие записи
        per_video = [v for v in per_video if v['info']['json'] not in removed_names]
        if removed_names:
            print(f"Удалено из кэша (аннотация отсутствует): {removed_names}")

        # Новые видео для обработки
        new_jsons = [f for f in json_files if f.name in new_names]
        print(f"Уже в кэше: {len(per_video)} видео")
        print(f"Новых для обработки: {len(new_jsons)} видео")
    else:
        per_video = []
        new_jsons = json_files  # все видео новые
        print(f"Создаётся новый кэш. Всего видео: {len(new_jsons)}")

    # Обрабатываем новые видео
    if new_jsons:
        use_filter = config.PERSON_FILTER.get('enabled', True)
        extractor = PoseFeatureExtractor(use_person_filter=use_filter)
        save_debug = config.PERSON_FILTER.get('save_debug_video', False)

        for jf in new_jsons:
            print(f"\n{'='*50}")
            print(f"  {'[НОВОЕ] ' if existing_cache is not None else ''}{jf.name}")

            with open(jf, 'r', encoding='utf-8') as f:
                ann = json.load(f)

            video_path = find_video(config.RAW_VIDEOS_DIR, ann['video'])
            if video_path is None:
                print(f"  ПРОПУСК: видео не найдено")
                continue

            # Извлекаем признаки (с фильтрацией)
            result = extractor.extract_full_video(video_path, save_debug_video=save_debug)
            if len(result) == 5:
                features, landmarks, fps, det_mask, filter_stats = result
            else:
                features, landmarks, fps, det_mask = result
                filter_stats = {}

            labels = create_phase_labels(len(features), ann.get('strokes', []))

            info = {
                'video': ann['video'],
                'json': jf.name,
                'fps': fps,
                'n_frames': len(features),
                'strokes': ann.get('strokes', []),
                'filter_stats': filter_stats,
            }

            per_video.append({
                'features': features,
                'labels': labels,
                'info': info,
            })

            # Статистика фаз
            unique, counts = np.unique(labels, return_counts=True)
            dist = {config.PHASE_NAMES[u]: int(c) for u, c in zip(unique, counts)}
            print(f"  Фазы: {dist}")

        extractor.close()
    else:
        print("Новых видео нет.")

    # Пересобираем общие массивы
    all_features, all_labels = _rebuild_aggregated(per_video)

    # Сохраняем кэш (без отдельного filter_stats)
    cache = {
        'per_video': per_video,
        'all_features': all_features,
        'all_labels': all_labels,
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'wb') as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\nКэш сохранён: {cache_path}")
    print(f"Всего видео: {len(per_video)}")
    print(f"Всего кадров: {len(all_features)}")
    print(f"Распределение: {dict(zip(*np.unique(all_labels, return_counts=True)))}")

    # Сводная статистика фильтрации (из info)
    if per_video:
        print(f"\n{'='*50}")
        print("СВОДКА ФИЛЬТРАЦИИ ИГРОКА:")
        totals = {}
        for v in per_video:
            fs = v['info'].get('filter_stats', {})
            for k, val in fs.items():
                totals[k] = totals.get(k, 0) + val
        for k, v in sorted(totals.items()):
            print(f"  {k}: {v}")

    return cache


def load_cache():
    """Загружает кэш признаков."""
    with open(config.FEATURES_CACHE_PATH, 'rb') as f:
        return pickle.load(f)