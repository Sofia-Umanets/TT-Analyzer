# TT Analyzer

Инструмент для автоматического анализа техники настольного тенниса по видео. Извлекает скелетные признаки через MediaPipe Pose, определяет фазы удара, классифицирует тип удара и детектирует ошибки техники.

## Архитектура

```
table_tennis_analyzer/
├── src/
│   ├── features/
│   │   ├── pose_features.py      # Извлечение 62 признаков из видео (MediaPipe)
│   │   └── person_filter.py      # Фильтрация целевого игрока в кадре
│   ├── models/
│   │   ├── phase_detector.py     # Conv1D + BiLSTM детектор фаз (idle/backswing/contact/follow-through)
│   │   ├── stroke_classifier.py  # Классификатор типов ударов
│   │   └── error_detector.py     # Attention + BiLSTM детектор ошибок техники (multi-label)
│   ├── data/
│   │   ├── dataset.py            # PyTorch Dataset для фаз и ударов
│   │   └── preprocessing.py      # Кэш признаков, разметка фаз, нормализация
│   └── utils/
│       ├── visualization.py
│       └── metrics.py
├── scripts/
│   ├── 01_extract_features.py    # Извлечение признаков → кэш
│   ├── 02_train_phase.py         # Обучение детектора фаз
│   ├── 03_train_classifier.py    # Обучение классификатора типов
│   ├── 04_train_errors.py        # Обучение детектора ошибок
│   ├── 05_evaluate_all.py        # Оценка всех моделей
│   ├── 06_auto_annotate.py       # Авторазметка видео
│   └── 07_analyze_video.py       # Полный анализ нового видео
├── web/
│   ├── backend/                  # FastAPI: REST API + ML inference
│   └── frontend/                 # React + Vite + Tailwind
├── annotator.py                  # Ручная разметка видео (CV2)
├── config.py                     # Конфигурация: пути, гиперпараметры, типы ударов
├── Dockerfile
└── docker-compose.yml
```

## Признаки

62 признака на кадр, 6 групп:

| Группа | Индексы | Описание |
|---|---|---|
| Углы суставов | 0–11 | Локоть, плечо, колено, бедро, запястье (обе стороны) |
| Относительные позиции | 12–23 | Запястья и локти относительно центра плеч |
| Корпус и стойка | 24–33 | Поворот, наклон, ширина стойки, высота бедер |
| Скорости и ускорения | 34–45 | Линейные скорости, ускорение запястий, угловые скорости |
| Фазовые | 46–53 | Направление движения запястий, расстояние до нейтрали |
| Симметрия и баланс | 54–61 | Разница углов, видимость запястий |

## Типы ударов

`drive_forehand`, `topspin_forehand`, `slice_forehand`, `drive_backhand`, `topspin_backhand`, `slice_backhand`, `other`

## Установка

```bash
pip install -r requirements.txt
```

Для GPU — установить PyTorch с CUDA отдельно (см. [GPU_SETUP.md](GPU_SETUP.md)).

## Быстрый старт

```bash
# 1. Извлечь признаки из всех видео
python scripts/01_extract_features.py

# 2. Обучить модели
python scripts/02_train_phase.py
python scripts/03_train_classifier.py
python scripts/04_train_errors.py

# 3. Анализ нового видео
python scripts/07_analyze_video.py path/to/video.mp4
```

## Веб-интерфейс

```bash
# С Docker
docker-compose up

# Без Docker
uvicorn web.backend.main:app --reload --port 8000
cd web/frontend && npm install && npm run dev
```

Бэкенд: `http://localhost:8000`  
Фронтенд: `http://localhost:5173`

## Разметка данных

```bash
python annotator.py path/to/video.mp4
```

Управление: `Space` — старт/стоп удара, `1–7` — тип удара, `q/w/e/...` — ошибки техники.

## Стек

- **Python 3.12**, PyTorch, MediaPipe Pose, OpenCV, scikit-learn
- **FastAPI** (бэкенд), **React + Vite + Tailwind** (фронтенд)
- **Docker** + nvidia-container-toolkit для GPU
