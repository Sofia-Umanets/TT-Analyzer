# Бэкенд анализатора настольного тенниса. Поддерживает CPU и NVIDIA CUDA.
#
# Сборка:  docker compose build
# Запуск:  docker compose up -d                                               (CPU)
#          docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d  (GPU)

FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    MEDIAPIPE_HOME=/opt/mediapipe \
    VIRTUAL_ENV=/venv \
    PATH="/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12-dev \
        python3.12-venv \
        ffmpeg \
        libgl1 \
        libegl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv /venv

WORKDIR /app

RUN pip install --no-cache-dir \
    "torch>=2.1,<3.0" \
    "torchvision>=0.16" \
    --index-url https://download.pytorch.org/whl/cu128


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


RUN python3 -c "\
import mediapipe as mp; \
p = mp.solutions.pose.Pose(model_complexity=1); p.close(); \
p = mp.solutions.pose.Pose(model_complexity=2); p.close(); \
print('MediaPipe models cached at', __import__(\"os\").environ[\"MEDIAPIPE_HOME\"])"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
