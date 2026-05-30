"""
Классификатор типов ударов (7 классов).
Attention + BiLSTM на нормализованной последовательности.
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from collections import Counter

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from src.data.dataset import StrokeDataset
from src.data.preprocessing import normalize_sequence


class StrokeClassifier(nn.Module):
    """Attention + BiLSTM классификатор типов ударов."""

    def __init__(self, input_size=config.NUM_FEATURES,
                 hidden_size=128, num_types=config.NUM_TYPES):
        super().__init__()

        self.attention = nn.Sequential(
            nn.Linear(input_size, 32),
            nn.Tanh(),
            nn.Linear(32, 1),
        )

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.3,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden_size * 2, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(0.3),
            nn.Linear(64, num_types),
        )

    def forward(self, x):
        """x: (batch, seq_len, features) → (batch, num_types)"""
        attn = torch.softmax(self.attention(x), dim=1)  # (B, T, 1)
        out, (h, _) = self.lstm(x)
        hidden = torch.cat([h[-2], h[-1]], dim=1)
        attended = (out * attn).sum(dim=1)
        combined = hidden + attended
        return self.head(combined)


class StrokeClassifierTrainer:
    """Обучение и инференс классификатора типов."""

    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"  [StrokeClassifier] device: {self.device}")
        self.model = None
        self.cfg = config.STROKE_CLASSIFIER

    def prepare_samples(self, per_video):
        """
        Собирает отдельные удары из кэша.

        Returns
        -------
        samples : list[dict]
            Каждый dict: features (n_frames, 62), type, errors, quality
        """
        samples = []
        for v in per_video:
            info = v['info']
            features = v['features']
            video_path_stem = Path(info['video']).stem

            for s in info['strokes']:
                start = s['start_frame']
                end = s['end_frame']

                if end >= len(features):
                    end = len(features) - 1
                if end - start < 3:
                    continue

                samples.append({
                    'features': features[start:end + 1],
                    'type': s.get('type', 'other'),
                    'errors': s.get('errors', []),
                    'quality': s.get('quality', 5),
                    'video': video_path_stem,
                    'stroke_id': s.get('id', 0),
                })

        print(f"  Собрано {len(samples)} ударов")
        types = Counter(s['type'] for s in samples)
        for t, c in sorted(types.items()):
            print(f"    {t}: {c}")

        return samples

    def train(self, samples):
        """Обучает классификатор."""
        print("\n" + "=" * 60)
        print("ОБУЧЕНИЕ КЛАССИФИКАТОРА ТИПОВ")
        print("=" * 60)

        tl = self.cfg['target_length']

        # Разбивка по видео, а не по отдельным ударам.
        # Удары из одного видео снимаются одним игроком при одном освещении,
        # поэтому разбивка по ударам создаёт утечку данных между train и val.
        videos = sorted({s['video'] for s in samples})
        if len(videos) > 1:
            train_vids, val_vids = train_test_split(videos, test_size=0.2, random_state=42)
            val_set = set(val_vids)
            train_s = [s for s in samples if s['video'] not in val_set]
            val_s   = [s for s in samples if s['video'] in val_set]
            if not val_s:       # если всё видео попало в train — берём его же для val
                val_s = train_s
        else:
            train_s, val_s = samples, samples
            print("  ⚠ Все удары из одного видео — val = train")

        train_ds = StrokeDataset(train_s, target_length=tl)
        val_ds = StrokeDataset(val_s, target_length=tl)

        train_loader = DataLoader(train_ds, batch_size=self.cfg['batch_size'],
                                  shuffle=True, drop_last=len(train_ds) > self.cfg['batch_size'])
        val_loader = DataLoader(val_ds, batch_size=self.cfg['batch_size'])

        print(f"  Train: {len(train_ds)}, Val: {len(val_ds)}")

        # Веса классов
        type_counts = Counter(s['type'] for s in train_s)
        weights = torch.FloatTensor([
            1.0 / (type_counts.get(config.IDX_TO_TYPE[i], 0) + 1)
            for i in range(config.NUM_TYPES)
        ]).to(self.device)
        weights = weights / weights.sum() * config.NUM_TYPES

        self.model = StrokeClassifier(
            hidden_size=self.cfg['hidden_size'],
        ).to(self.device)

        best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.cfg['lr'])
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, patience=8, factor=0.5)
        criterion = nn.CrossEntropyLoss(weight=weights)

        best_acc = 0
        history = {'loss': [], 'val_acc': []}

        for epoch in range(1, self.cfg['epochs'] + 1):
            self.model.train()
            total_loss = 0
            for batch in train_loader:
                X = batch['features'].to(self.device)
                y = batch['type'].to(self.device)
                optimizer.zero_grad()
                out = self.model(X)
                loss = criterion(out, y)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()
            avg_loss = total_loss / len(train_loader)

            # Val
            acc = self._evaluate_acc(val_loader)
            scheduler.step(1 - acc)

            history['loss'].append(avg_loss)
            history['val_acc'].append(acc)

            improved = ""
            if acc > best_acc:
                best_acc = acc
                best_state = {k: v.cpu().clone()
                              for k, v in self.model.state_dict().items()}
                improved = " ← best"

            if epoch % 10 == 0 or improved:
                print(f"  Epoch {epoch:3d}/{self.cfg['epochs']} | "
                      f"Loss: {avg_loss:.4f} | Val Acc: {acc:.3f}{improved}")

        self.model.load_state_dict(best_state)
        self.model.to(self.device)

        print(f"\n  Лучшая Val Acc: {best_acc:.3f}")
        self._print_report(val_loader)
        self._save_global_importance(val_loader)

        return history

    def predict(self, features_sequence):
        """
        Предсказывает тип удара.

        Parameters
        ----------
        features_sequence : np.ndarray (n_frames, 62)

        Returns
        -------
        type_name : str
        probabilities : np.ndarray (7,)
        """
        if self.model is None:
            raise RuntimeError("Модель не обучена / не загружена")

        self.model.eval()
        tl = self.cfg['target_length']
        feat = normalize_sequence(features_sequence, tl)
        feat = np.nan_to_num(feat, nan=0.0, posinf=5.0, neginf=-5.0)

        try:
            x = torch.FloatTensor(feat).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits = self.model(x)
                probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        except RuntimeError as e:
            if self.device.type != 'cuda' or 'cuda' not in str(e).lower():
                raise
            print(f"  [WARN] StrokeClassifier CUDA ошибка, fallback CPU: {e}")
            torch.cuda.empty_cache()
            self.model = self.model.cpu()
            self.device = torch.device('cpu')
            x = torch.FloatTensor(feat).unsqueeze(0)
            with torch.no_grad():
                logits = self.model(x)
                probs = torch.softmax(logits, dim=-1).numpy()[0]

        idx = probs.argmax()
        return config.IDX_TO_TYPE[idx], probs

    def _evaluate_acc(self, loader):
        self.model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for batch in loader:
                X = batch['features'].to(self.device)
                y = batch['type'].to(self.device)
                pred = self.model(X).argmax(dim=-1)
                correct += (pred == y).sum().item()
                total += len(y)
        return correct / total if total > 0 else 0

    def _print_report(self, loader):
        self.model.eval()
        all_pred, all_true = [], []
        with torch.no_grad():
            for batch in loader:
                X = batch['features'].to(self.device)
                y = batch['type']
                pred = self.model(X).argmax(dim=-1).cpu()
                all_pred.extend(pred.numpy())
                all_true.extend(y.numpy())

        present = sorted(set(all_true) | set(all_pred))
        names = [config.IDX_TO_TYPE.get(i, f'type_{i}') for i in present]
        print(classification_report(
            all_true, all_pred, labels=present,
            target_names=names, zero_division=0))

    def _save_global_importance(self, val_loader):
        """Среднее gradient-based importance по val-сету → models/feature_importance.json."""
        import json
        self.model.eval()
        all_grads = []

        try:
            for batch in val_loader:
                X = batch['features'].to(self.device).detach().requires_grad_(True)
                self.model.zero_grad()
                logits = self.model(X)
                pred = logits.argmax(dim=-1)
                score = logits.gather(1, pred.unsqueeze(1)).sum()
                score.backward()
                if X.grad is not None:
                    grads = X.grad.abs().mean(dim=1).detach().cpu().numpy()
                    all_grads.append(grads)
        except Exception as e:
            print(f"  ⚠ Важность признаков не вычислена: {e}")
            return

        if not all_grads:
            return

        mean_grads = np.vstack(all_grads).mean(axis=0)
        mean_grads = mean_grads / (mean_grads.sum() + 1e-8)
        importance = {
            config.FEATURE_NAMES[i]: round(float(v), 6)
            for i, v in enumerate(mean_grads)
            if i < len(config.FEATURE_NAMES)
        }

        imp_path = config.MODELS_DIR / "feature_importance.json"
        with open(imp_path, "w") as f:
            json.dump(importance, f, indent=2)
        print(f"  Важность признаков сохранена: {imp_path.name}")

    def save(self, path=None):
        path = path or config.CLASSIFIER_MODEL_PATH
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'config': self.cfg,
        }, path)
        print(f"  Модель сохранена: {path}")

    def load(self, path=None):
        path = path or config.CLASSIFIER_MODEL_PATH
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        self.cfg = ckpt.get('config', config.STROKE_CLASSIFIER)

        self.model = StrokeClassifier(
            hidden_size=self.cfg['hidden_size'],
        ).to(self.device)
        self.model.load_state_dict(ckpt['model_state_dict'])
        self.model.eval()
        print(f"  Модель загружена: {path}")