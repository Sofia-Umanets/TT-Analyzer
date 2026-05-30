#!/usr/bin/env python3
"""
ШАГ 1: Извлечение признаков из всех видео и создание кэша.

Запуск:
    python scripts/01_extract_features.py [--force]
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data.preprocessing import build_features_cache


def main():
    parser = argparse.ArgumentParser(description="Извлечение признаков из видео")
    parser.add_argument('--force', action='store_true',
                        help='Пересоздать кэш даже если существует')
    args = parser.parse_args()

    print("=" * 60)
    print("ШАГ 1: ИЗВЛЕЧЕНИЕ ПРИЗНАКОВ")
    print("=" * 60)

    cache = build_features_cache(force=args.force)

    print(f"\nГотово!")
    print(f"  Видео: {len(cache['per_video'])}")
    print(f"  Кадров: {len(cache['all_features'])}")


if __name__ == "__main__":
    main()