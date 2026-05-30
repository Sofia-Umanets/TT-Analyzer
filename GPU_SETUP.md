# Запуск на GPU (CUDA)

## Требования

| Компонент | Минимум |
|-----------|---------|
| Видеокарта | NVIDIA (любая с поддержкой CUDA ≥ 12.1) |
| Драйвер NVIDIA | ≥ 525 |
| Docker | ≥ 24.0 |
| NVIDIA Container Toolkit | любая актуальная версия |

---

## 1. Установка драйвера NVIDIA (если не установлен)

```bash
# Ubuntu
sudo apt install nvidia-driver-535
sudo reboot
nvidia-smi   # проверка: должна показать карту и версию CUDA
```

---

## 2. Установка NVIDIA Container Toolkit (для Docker)

```bash
# Добавляем репозиторий
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor \
  -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 3. Сборка и запуск контейнера

### Вариант A — docker-compose (рекомендуется)

```bash
cd /путь/до/table_tennis_analyzer

# Сборка (первый раз ~5–10 минут из-за загрузки PyTorch)
docker compose build

# Запуск
docker compose up -d

# Логи (проверяем, что GPU подхватился)
docker compose logs -f backend
```

В логах должно появиться что-то вроде:
```
[ML Bridge] GPU: NVIDIA GeForce RTX 3050 (4096 MB)
[ML Bridge] Загрузка моделей на cuda:0...
```

### Вариант B — docker run напрямую

```bash
# Сборка
docker build -t tt-analyzer .

# Запуск с GPU
docker run --gpus all -p 8000:8000 \
  -v $(pwd)/storage:/app/storage \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/data:/app/data \
  tt-analyzer

# Запуск без GPU (CPU-only)
docker run -p 8000:8000 \
  -e CUDA_VISIBLE_DEVICES='' \
  -v $(pwd)/storage:/app/storage \
  tt-analyzer
```

---

## 4. Локальная разработка без Docker

Установи PyTorch с CUDA вручную (до `pip install -r requirements.txt`):

```bash
# CUDA 12.1
pip install "torch>=2.1" torchvision \
    --index-url https://download.pytorch.org/whl/cu121

# Остальные зависимости
pip install -r requirements.txt
```

Проверка в Python:
```python
import torch
print(torch.cuda.is_available())        # True
print(torch.cuda.get_device_name(0))    # NVIDIA GeForce ...
```

---

## 5. Принудительное отключение GPU

Если нужно запустить на CPU (например, CUDA не установлена):

```bash
# Локально
CUDA_VISIBLE_DEVICES='' python scripts/03_train_classifier.py

# В docker-compose.yml раскомментируй:
# CUDA_VISIBLE_DEVICES: ""
```

---

## 6. Проверка использования GPU во время обучения

```bash
# В отдельном терминале
watch -n 1 nvidia-smi

# Или внутри контейнера
docker exec -it <container_id> nvidia-smi
```

При обучении `GPU-Util` должен быть > 0%.

---

## 7. Замечания для карты с 4 ГБ памяти

Модели небольшие (BiLSTM + Attention), поэтому 4 ГБ более чем достаточно.
Если вдруг возникнет `CUDA out of memory` при обучении — уменьши `batch_size` в `config.py`:

```python
STROKE_CLASSIFIER = { 'batch_size': 8, ... }   # было 16
PHASE_DETECTOR    = { 'batch_size': 8, ... }
ERROR_DETECTOR    = { 'batch_size': 8, ... }
```
