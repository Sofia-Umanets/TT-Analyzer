"""
LSTM детектор фаз удара: idle / backswing / contact / follow_through.
Покадровая классификация с временным контекстом.
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from src.data.dataset import PhaseDataset


class PhaseDetectorLSTM(nn.Module):
    """Conv1D + BiLSTM для покадровой классификации фаз."""

    def __init__(self, input_size=config.NUM_FEATURES,
                 hidden_size=128, num_classes=config.NUM_PHASES):
        super().__init__()

        self.conv1 = nn.Conv1d(input_size, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(64, 64, kernel_size=3, padding=1)
        self.bn = nn.BatchNorm1d(64)

        self.lstm = nn.LSTM(
            input_size=64,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.3,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden_size * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        """x: (batch, seq_len, features) → (batch, seq_len, num_classes)"""
        c = x.permute(0, 2, 1)
        c = torch.relu(self.conv1(c))
        c = torch.relu(self.bn(self.conv2(c)))
        c = c.permute(0, 2, 1)

        out, _ = self.lstm(c)
        return self.head(out)


class PhaseDetectorTrainer:
    """Обучение и инференс детектора фаз."""

    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"  [PhaseDetector] device: {self.device}")
        self.model = None
        self.scaler = StandardScaler()
        self.cfg = config.PHASE_DETECTOR
        self._val_per_video: list = []  # заполняется после вызова train()



    def train(self, per_video):
        """
        Обучает модель на данных из кэша.

        Parameters
        ----------
        per_video : list[dict]
            Каждый dict: features (N,62), labels (N,), info (dict)
        """
        print("\n" + "=" * 60)
        print("ОБУЧЕНИЕ ДЕТЕКТОРА ФАЗ (LSTM)")
        print("=" * 60)

        features_list = [v['features'] for v in per_video]
        labels_list = [v['labels'] for v in per_video]

        # Разбивка по видео: val-записи не пересекаются с обучающими.
        n = len(features_list)
        indices = list(range(n))
        if n > 3:
            train_idx, val_idx = train_test_split(indices, test_size=0.2, random_state=42)
        else:
            train_idx, val_idx = indices, indices
            print("  ⚠ Мало видео — val = train")

        # Scaler обучается только на train-данных, чтобы не утекала статистика val.
        self.scaler.fit(np.vstack([features_list[i] for i in train_idx]))
        features_list_scaled = [self.scaler.transform(f) for f in features_list]

        # Сохраняем val-видео для честной оценки на отложенной выборке.
        self._val_per_video = [per_video[i] for i in val_idx]

        train_feat = [features_list_scaled[i] for i in train_idx]
        train_lab = [labels_list[i] for i in train_idx]
        val_feat = [features_list_scaled[i] for i in val_idx]
        val_lab = [labels_list[i] for i in val_idx]

        seq_len = self.cfg['seq_length']
        overlap = self.cfg['overlap']

        train_ds = PhaseDataset(train_feat, train_lab, seq_len, overlap)
        val_ds = PhaseDataset(val_feat, val_lab, seq_len, overlap)

        print(f"  Train sequences: {len(train_ds)}")
        print(f"  Val sequences:   {len(val_ds)}")
        print(f"  Device: {self.device}")

        train_loader = DataLoader(train_ds, batch_size=self.cfg['batch_size'],
                                  shuffle=True, drop_last=True)
        val_loader = DataLoader(val_ds, batch_size=self.cfg['batch_size'])

        all_labels_flat = np.concatenate(train_lab)
        counts = np.bincount(all_labels_flat, minlength=config.NUM_PHASES)
        weights = 1.0 / (counts + 1)
        weights = weights / weights.sum() * config.NUM_PHASES
        class_weights = torch.FloatTensor(weights).to(self.device)
        print(f"  Class weights: {weights.round(3)}")

        self.model = PhaseDetectorLSTM(
            input_size=config.NUM_FEATURES,
            hidden_size=self.cfg['hidden_size'],
        ).to(self.device)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.cfg['lr'])
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, patience=7, factor=0.5)
        criterion = nn.CrossEntropyLoss(weight=class_weights)

        best_f1 = 0
        best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
        history = {'loss': [], 'val_f1': []}

        for epoch in range(1, self.cfg['epochs'] + 1):
            # --- train ---
            self.model.train()
            total_loss = 0
            for X, y in train_loader:
                X, y = X.to(self.device), y.to(self.device)
                optimizer.zero_grad()
                out = self.model(X)
                loss = criterion(out.reshape(-1, config.NUM_PHASES), y.reshape(-1))
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()
            avg_loss = total_loss / len(train_loader)

            # --- val ---
            val_f1 = self._evaluate_f1(val_loader)
            scheduler.step(1 - val_f1)

            history['loss'].append(avg_loss)
            history['val_f1'].append(val_f1)

            improved = ""
            if val_f1 > best_f1:
                best_f1 = val_f1
                best_state = {k: v.cpu().clone() for k, v in
                              self.model.state_dict().items()}
                improved = " ← best"

            if epoch % 5 == 0 or improved:
                print(f"  Epoch {epoch:3d}/{self.cfg['epochs']} | "
                      f"Loss: {avg_loss:.4f} | Val F1: {val_f1:.3f}{improved}")

        self.model.load_state_dict(best_state)
        self.model.to(self.device)

        print(f"\n  Лучший Val F1: {best_f1:.3f}")
        self._print_report(val_loader)

        return history

    def _evaluate_f1(self, loader):
        self.model.eval()
        all_pred, all_true = [], []
        with torch.no_grad():
            for X, y in loader:
                X = X.to(self.device)
                pred = self.model(X).argmax(dim=-1).cpu().numpy().flatten()
                all_pred.extend(pred)
                all_true.extend(y.numpy().flatten())
        return f1_score(all_true, all_pred, average='macro', zero_division=0)

    def _print_report(self, loader):
        self.model.eval()
        all_pred, all_true = [], []
        with torch.no_grad():
            for X, y in loader:
                X = X.to(self.device)
                pred = self.model(X).argmax(dim=-1).cpu().numpy().flatten()
                all_pred.extend(pred)
                all_true.extend(y.numpy().flatten())
        print(classification_report(
            all_true, all_pred,
            target_names=config.PHASE_NAMES, zero_division=0))

    # ------------------------------------------------------------------
    # Инференс
    # ------------------------------------------------------------------

    def predict_video(self, features):
        """
        Предсказывает фазы для всего видео.

        Returns
        -------
        phases : np.ndarray (N,)
        probs : np.ndarray (N, 4)
        """
        if self.model is None:
            raise RuntimeError("Модель не обучена / не загружена")

        self.model.eval()
        feat_scaled = self.scaler.transform(features)

        # NaN/Inf после StandardScaler (std=0 у редких признаков) вызывают
        # CUDA "unspecified launch failure" внутри LSTM-ядра
        if not np.isfinite(feat_scaled).all():
            feat_scaled = np.nan_to_num(feat_scaled, nan=0.0, posinf=5.0, neginf=-5.0)

        n = len(feat_scaled)
        seq_len = self.cfg['seq_length']
        step = seq_len // 2

        accum = np.zeros((n, config.NUM_PHASES))
        counts = np.zeros(n)

        # Синхронизируем и чистим CUDA-кэш перед инференсом:
        # MediaPipe использует EGL/OpenGL и может оставить GPU в несогласованном состоянии
        if self.device.type == 'cuda':
            torch.cuda.synchronize()
            torch.cuda.empty_cache()

        with torch.no_grad():
            for start in range(0, n, step):
                end = min(start + seq_len, n)
                seg = feat_scaled[start:end]
                if len(seg) < seq_len:
                    pad = np.zeros((seq_len - len(seg), config.NUM_FEATURES))
                    seg = np.vstack([seg, pad])

                try:
                    x = torch.FloatTensor(seg).unsqueeze(0).to(self.device)
                    out = self.model(x)
                    probs = torch.softmax(out, dim=-1).cpu().numpy()[0]
                except RuntimeError as e:
                    if self.device.type != 'cuda' or 'cuda' not in str(e).lower():
                        raise
                    # CUDA-контекст повреждён — переключаемся на CPU и дорабатываем
                    print(f"  [WARN] PhaseDetector CUDA ошибка (итерация {start}), fallback CPU: {e}")
                    torch.cuda.empty_cache()
                    self.model = self.model.cpu()
                    self.device = torch.device('cpu')
                    x = torch.FloatTensor(seg).unsqueeze(0)
                    out = self.model(x)
                    probs = torch.softmax(out, dim=-1).numpy()[0]

                actual = min(end - start, seq_len)
                accum[start:start + actual] += probs[:actual]
                counts[start:start + actual] += 1

        counts = np.maximum(counts, 1)
        avg_probs = accum / counts[:, None]
        phases = avg_probs.argmax(axis=1)
        phases = self._smooth(phases)

        return phases, avg_probs

    @staticmethod
    def _smooth(phases, min_len=3):
        """Убирает одиночные выбросы и слишком короткие сегменты."""
        s = phases.copy()
        # Медианный фильтр
        for i in range(1, len(s) - 1):
            if s[i] != s[i - 1] and s[i] != s[i + 1]:
                s[i] = s[i - 1]
        # Короткие сегменты
        i = 0
        while i < len(s):
            j = i
            while j < len(s) and s[j] == s[i]:
                j += 1
            if j - i < min_len and s[i] != 0:
                prev = s[max(0, i - 1)]
                s[i:j] = prev
            i = j
        return s

    def extract_strokes(self, phases, fps):
        """Извлекает удары из последовательности фаз."""
        strokes = []
        cur = None
        min_frames = config.PHASE_DETECTOR['min_stroke_frames']

        for i, ph in enumerate(phases):
            if ph == 1 and cur is None:
                cur = {'start_frame': i, 'contact_frame': None, 'end_frame': None}
            elif ph == 2 and cur is not None and cur['contact_frame'] is None:
                cur['contact_frame'] = i
            elif ph == 0 and cur is not None:
                cur['end_frame'] = i - 1
                if cur['contact_frame'] is None:
                    cur['contact_frame'] = (cur['start_frame'] + cur['end_frame']) // 2
                if cur['end_frame'] - cur['start_frame'] >= min_frames:
                    strokes.append(cur)
                cur = None
            elif ph == 3 and cur is not None:
                pass  # follow_through продолжается

        if cur is not None:
            cur['end_frame'] = len(phases) - 1
            if cur['contact_frame'] is None:
                cur['contact_frame'] = (cur['start_frame'] + cur['end_frame']) // 2
            if cur['end_frame'] - cur['start_frame'] >= min_frames:
                strokes.append(cur)

        for i, s in enumerate(strokes, 1):
            s['id'] = i
            s['start_time'] = round(s['start_frame'] / fps, 3)
            s['contact_time'] = round(s['contact_frame'] / fps, 3)
            s['end_time'] = round(s['end_frame'] / fps, 3)

        return strokes

    # ------------------------------------------------------------------
    # Сохранение / загрузка
    # ------------------------------------------------------------------

    def save(self, path=None):
        path = path or config.PHASE_MODEL_PATH
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'scaler_mean': self.scaler.mean_,
            'scaler_scale': self.scaler.scale_,
            'config': self.cfg,
        }, path)
        print(f"  Модель сохранена: {path}")

    def load(self, path=None):
        path = path or config.PHASE_MODEL_PATH
        ckpt = torch.load(path, map_location=self.device, weights_only=False)

        self.cfg = ckpt.get('config', config.PHASE_DETECTOR)
        self.scaler = StandardScaler()
        self.scaler.mean_ = ckpt['scaler_mean']
        self.scaler.scale_ = ckpt['scaler_scale']

        self.model = PhaseDetectorLSTM(
            input_size=config.NUM_FEATURES,
            hidden_size=self.cfg['hidden_size'],
        ).to(self.device)
        self.model.load_state_dict(ckpt['model_state_dict'])
        self.model.eval()
        print(f"  Модель загружена: {path}")