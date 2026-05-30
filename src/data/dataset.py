"""
PyTorch Dataset классы для всех задач.
"""

import numpy as np
import torch
from torch.utils.data import Dataset

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from .preprocessing import normalize_sequence


class PhaseDataset(Dataset):
    """
    Датасет для детекции фаз.
    Нарезает видео на перекрывающиеся последовательности.
    """

    def __init__(self, features_list, labels_list, seq_length=64, overlap=32):
        self.sequences = []
        self.targets = []

        step = seq_length - overlap

        for features, labels in zip(features_list, labels_list):
            n = len(features)
            for start in range(0, n - seq_length + 1, step):
                end = start + seq_length
                self.sequences.append(features[start:end])
                self.targets.append(labels[start:end])

        self.sequences = np.array(self.sequences)
        self.targets = np.array(self.targets)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return (torch.FloatTensor(self.sequences[idx]),
                torch.LongTensor(self.targets[idx]))


class StrokeDataset(Dataset):
    """
    Датасет для классификации типов ударов и детекции ошибок.
    Каждый пример — один удар, нормализованный к target_length.
    """

    def __init__(self, samples, target_length=30):
        """
        Parameters
        ----------
        samples : list[dict]
            Каждый dict содержит:
            - features: np.ndarray (n_frames, 62)
            - type: str
            - errors: list[str]
            - quality: int
        """
        self.samples = samples
        self.target_length = target_length

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]

        # Нормализуем длину
        feat = normalize_sequence(s['features'], self.target_length)
        feat = torch.FloatTensor(feat)

        # Тип удара
        type_idx = config.TYPE_TO_IDX.get(s.get('type', 'other'), 6)

        # Ошибки (multi-hot)
        errors = torch.zeros(config.NUM_ERRORS)
        for err in s.get('errors', []):
            if err in config.ERROR_TO_IDX:
                errors[config.ERROR_TO_IDX[err]] = 1.0

        # Качество [0, 1]
        quality = (s.get('quality', 5) - 1) / 9.0

        return {
            'features': feat,
            'type': torch.tensor(type_idx, dtype=torch.long),
            'errors': errors,
            'quality': torch.tensor([quality], dtype=torch.float32),
        }