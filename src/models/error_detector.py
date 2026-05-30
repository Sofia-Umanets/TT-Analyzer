"""
Детектор ошибок техники (multi-label classification).
Модифицирован для учёта типа удара (one-hot на входе).
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from collections import Counter

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from src.data.dataset import StrokeDataset
from src.data.preprocessing import normalize_sequence


class ErrorDetector(nn.Module):
    """
    Attention + BiLSTM для multi-label детекции ошибок.
    Также предсказывает оценку качества.
    Вход: признаки [batch, seq_len, features] + тип удара [batch]
    """

    def __init__(self, input_size=config.NUM_FEATURES,
                 hidden_size=128,
                 num_errors=config.NUM_ERRORS,
                 num_types=config.NUM_TYPES):
        super().__init__()
        self.num_types = num_types
        combined_size = input_size + num_types 

        self.attention = nn.Sequential(
            nn.Linear(combined_size, 32),
            nn.Tanh(),
            nn.Linear(32, 1),
        )

        self.lstm = nn.LSTM(
            input_size=combined_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.3,
        )

        self.shared = nn.Sequential(
            nn.Linear(hidden_size * 2, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
        )

        self.error_head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_errors),
        )

        self.quality_head = nn.Linear(64, 1)

    def forward(self, x, stroke_type=None):
        """
        x: [batch, seq_len, input_size]
        stroke_type: [batch] с индексами классов (int) или None
        """
        if stroke_type is None:
            # fallback – используем нули (например, при инференсе без типа)
            type_one_hot = torch.zeros(x.size(0), self.num_types).to(x.device)
        else:
            # приводим к shape [batch]
            if stroke_type.dim() == 2 and stroke_type.size(1) == 1:
                stroke_type = stroke_type.squeeze(1)
            # one-hot
            type_one_hot = torch.nn.functional.one_hot(
                stroke_type, num_classes=self.num_types
            ).float()

        # добавляем one-hot к каждому кадру
        type_one_hot = type_one_hot.unsqueeze(1).expand(-1, x.size(1), -1)
        x = torch.cat([x, type_one_hot], dim=-1)   # [batch, seq_len, combined_size]

        # attention
        attn = torch.softmax(self.attention(x), dim=1)   # [batch, seq_len, 1]
        lstm_out, (h, _) = self.lstm(x)                  # [batch, seq_len, hidden*2]
        hidden = torch.cat([h[-2], h[-1]], dim=1)        # последние слои BiLSTM
        attended = (lstm_out * attn).sum(dim=1)           # взвешенная сумма
        combined = hidden + attended                      # skip connection

        shared = self.shared(combined)

        return {
            'errors': self.error_head(shared),                 # raw logits
            'quality': torch.sigmoid(self.quality_head(shared)),
        }


class ErrorDetectorTrainer:
    """Обучение детектора ошибок."""

    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"  [ErrorDetector] device: {self.device}")
        self.model = None
        self.cfg = config.ERROR_DETECTOR

    def train(self, samples):
        """Обучает детектор ошибок."""
        print("\n" + "=" * 60)
        print("ОБУЧЕНИЕ ДЕТЕКТОРА ОШИБОК")
        print("=" * 60)

        print(f"  Всего ударов: {len(samples)}")
        error_counts = Counter()
        for s in samples:
            for e in s.get('errors', []):
                error_counts[e] += 1
        print(f"  Ошибки в данных:")
        for e, c in sorted(error_counts.items()):
            print(f"    {e}: {c}")

        tl = self.cfg['target_length']

        # Разбивка по видео: val-удары не пересекаются с обучающими записями
        # (исключает утечку данных от одного игрока).
        videos = sorted({s['video'] for s in samples})
        if len(videos) > 1:
            train_vids, val_vids = train_test_split(videos, test_size=0.2, random_state=42)
            val_set = set(val_vids)
            train_s = [s for s in samples if s['video'] not in val_set]
            val_s   = [s for s in samples if s['video'] in val_set]
            if not val_s:
                val_s = train_s
        else:
            train_s, val_s = samples, samples
            print("  ⚠ Все удары из одного видео — val = train")

        train_ds = StrokeDataset(train_s, target_length=tl)
        val_ds = StrokeDataset(val_s, target_length=tl)

        train_loader = DataLoader(train_ds, batch_size=self.cfg['batch_size'],
                                  shuffle=True, drop_last=len(train_ds) > self.cfg['batch_size'])
        val_loader = DataLoader(val_ds, batch_size=self.cfg['batch_size'])

        # pos_weight для BCEWithLogitsLoss (баланс классов)
        all_errors = np.array([
            [1 if e in s.get('errors', []) else 0 for e in config.ERROR_TYPES]
            for s in train_s
        ])
        pos_counts = all_errors.sum(axis=0) + 1
        neg_counts = len(train_s) - pos_counts + 1
        pos_weight = torch.FloatTensor(neg_counts / pos_counts).to(self.device)

        self.model = ErrorDetector(
            hidden_size=self.cfg['hidden_size'],
            num_types=config.NUM_TYPES,          # передаём количество типов
        ).to(self.device)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.cfg['lr'])
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, patience=10, factor=0.5)

        error_criterion = nn.BCEWithLogitsLoss(reduction='none')
        quality_criterion = nn.MSELoss()

        best_val_loss = float('inf')
        best_state = None
        history = {'loss': [], 'val_loss': [], 'val_error_f1': []}

        for epoch in range(1, self.cfg['epochs'] + 1):
            self.model.train()
            total_loss = 0

            for batch in train_loader:
                X = batch['features'].to(self.device)
                stroke_type = batch['type'].to(self.device)
                errors_true = batch['errors'].to(self.device)
                quality_true = batch['quality'].to(self.device)

                optimizer.zero_grad()
                out = self.model(X, stroke_type=stroke_type)

                # взвешенный BCE
                bce = error_criterion(out['errors'], errors_true)
                weight_mask = torch.where(errors_true == 1,
                                          pos_weight.unsqueeze(0),
                                          torch.ones_like(errors_true))
                loss_err = (bce * weight_mask).mean()
                loss_q = quality_criterion(out['quality'], quality_true)

                loss = loss_err + 0.2 * loss_q
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(train_loader)

            # validation
            val_loss, val_f1 = self._evaluate(val_loader, error_criterion,
                                               quality_criterion, pos_weight)
            scheduler.step(val_loss)

            history['loss'].append(avg_loss)
            history['val_loss'].append(val_loss)
            history['val_error_f1'].append(val_f1)

            improved = ""
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.cpu().clone()
                              for k, v in self.model.state_dict().items()}
                improved = " ← best"

            if epoch % 10 == 0 or improved:
                print(f"  Epoch {epoch:3d}/{self.cfg['epochs']} | "
                      f"Loss: {avg_loss:.4f} | Val: {val_loss:.4f} | "
                      f"F1: {val_f1:.3f}{improved}")

        self.model.load_state_dict(best_state)
        self.model.to(self.device)

        print(f"\n  Лучший Val Loss: {best_val_loss:.4f}")
        self._print_error_report(val_loader)

        return history

    def _evaluate(self, loader, err_crit, q_crit, pos_weight):
        self.model.eval()
        total_loss = 0
        all_pred, all_true = [], []

        with torch.no_grad():
            for batch in loader:
                X = batch['features'].to(self.device)
                stroke_type = batch['type'].to(self.device)
                errors_true = batch['errors'].to(self.device)
                quality_true = batch['quality'].to(self.device)

                out = self.model(X, stroke_type=stroke_type)

                bce = err_crit(out['errors'], errors_true)
                wm = torch.where(errors_true == 1,
                                 pos_weight.unsqueeze(0),
                                 torch.ones_like(errors_true))
                loss = (bce * wm).mean() + 0.2 * q_crit(out['quality'], quality_true)
                total_loss += loss.item()

                pred = (torch.sigmoid(out['errors']) > self.cfg['error_threshold']).float()
                all_pred.append(pred.cpu().numpy())
                all_true.append(errors_true.cpu().numpy())

        avg_loss = total_loss / len(loader)
        all_pred = np.vstack(all_pred)
        all_true = np.vstack(all_true)

        tp = ((all_pred == 1) & (all_true == 1)).sum()
        fp = ((all_pred == 1) & (all_true == 0)).sum()
        fn = ((all_pred == 0) & (all_true == 1)).sum()
        prec = tp / (tp + fp + 1e-8)
        rec = tp / (tp + fn + 1e-8)
        f1 = 2 * prec * rec / (prec + rec + 1e-8)

        return avg_loss, f1

    def _print_error_report(self, loader):
        self.model.eval()
        all_pred, all_true = [], []

        with torch.no_grad():
            for batch in loader:
                X = batch['features'].to(self.device)
                stroke_type = batch['type'].to(self.device)
                out = self.model(X, stroke_type=stroke_type)
                pred = (torch.sigmoid(out['errors']) > self.cfg['error_threshold']).float()
                all_pred.append(pred.cpu().numpy())
                all_true.append(batch['errors'].numpy())

        all_pred = np.vstack(all_pred)
        all_true = np.vstack(all_true)

        print("\n  Детекция ошибок по типам:")
        for i, name in enumerate(config.ERROR_TYPES):
            support = int(all_true[:, i].sum())
            if support == 0:
                continue
            tp = ((all_pred[:, i] == 1) & (all_true[:, i] == 1)).sum()
            fp = ((all_pred[:, i] == 1) & (all_true[:, i] == 0)).sum()
            fn = ((all_pred[:, i] == 0) & (all_true[:, i] == 1)).sum()
            p = tp / (tp + fp + 1e-8)
            r = tp / (tp + fn + 1e-8)
            f = 2 * p * r / (p + r + 1e-8)
            print(f"    {name:25s} | n={support:3d} | P={p:.2f} R={r:.2f} F1={f:.2f}")

    def predict(self, features_sequence, stroke_type):
        """
        Parameters
        ----------
        features_sequence : np.ndarray (n_frames, 62)
        stroke_type : int   индекс типа удара (0..6)

        Returns
        -------
        errors : list[str]
        quality : float (1-10)
        error_probs : dict[str, float]
        """
        if self.model is None:
            raise RuntimeError("Модель не обучена / не загружена")

        self.model.eval()
        tl = self.cfg['target_length']
        feat = normalize_sequence(features_sequence, tl)
        feat = np.nan_to_num(feat, nan=0.0, posinf=5.0, neginf=-5.0)

        try:
            x = torch.FloatTensor(feat).unsqueeze(0).to(self.device)
            type_tensor = torch.LongTensor([stroke_type]).to(self.device)
            with torch.no_grad():
                out = self.model(x, stroke_type=type_tensor)
                err_probs = torch.sigmoid(out['errors']).cpu().numpy()[0]
                quality = out['quality'].cpu().item() * 9 + 1
        except RuntimeError as e:
            if self.device.type != 'cuda' or 'cuda' not in str(e).lower():
                raise
            print(f"  [WARN] ErrorDetector CUDA ошибка, fallback CPU: {e}")
            torch.cuda.empty_cache()
            self.model = self.model.cpu()
            self.device = torch.device('cpu')
            x = torch.FloatTensor(feat).unsqueeze(0)
            type_tensor = torch.LongTensor([stroke_type])
            with torch.no_grad():
                out = self.model(x, stroke_type=type_tensor)
                err_probs = torch.sigmoid(out['errors']).numpy()[0]
                quality = out['quality'].item() * 9 + 1

        threshold = self.cfg['error_threshold']
        errors = [config.IDX_TO_ERROR[i]
                  for i, p in enumerate(err_probs) if p > threshold]
        probs_dict = {config.IDX_TO_ERROR[i]: float(p)
                      for i, p in enumerate(err_probs)}

        return errors, quality, probs_dict

    def save(self, path=None):
        path = path or config.ERROR_MODEL_PATH
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'config': self.cfg,
        }, path)
        print(f"  Модель сохранена: {path}")

    def load(self, path=None):
        path = path or config.ERROR_MODEL_PATH
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        self.cfg = ckpt.get('config', config.ERROR_DETECTOR)

        self.model = ErrorDetector(
            hidden_size=self.cfg['hidden_size'],
            num_types=config.NUM_TYPES,          # обязательно передаём
        ).to(self.device)
        self.model.load_state_dict(ckpt['model_state_dict'])
        self.model.eval()
        print(f"  Модель загружена: {path}")