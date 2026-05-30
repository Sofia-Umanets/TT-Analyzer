"""Визуализация результатов."""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config


PHASE_COLORS = {0: 'lightgray', 1: 'skyblue', 2: 'red', 3: 'lightgreen'}


def plot_phases(features, pred_phases, true_labels=None,
                title="Phase Detection", save_path=None):
    """Визуализация предсказанных фаз на timeline."""
    fig, axes = plt.subplots(3, 1, figsize=(16, 9),
                              gridspec_kw={'height_ratios': [2, 1, 1]})
    n = len(pred_phases)
    x = np.arange(n)

    # 1. Скорость запястья + фазы
    ax = axes[0]
    if features.shape[1] > 34:
        speed = features[:, 34]
        ax.plot(x, speed, 'b-', linewidth=0.8, alpha=0.7)
        for ph, color in PHASE_COLORS.items():
            mask = pred_phases == ph
            ax.fill_between(x, 0, speed.max(), where=mask,
                           alpha=0.15, color=color)
    ax.set_ylabel('Wrist Speed')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    # 2. Предсказанные фазы
    ax = axes[1]
    for i in range(n):
        ax.axvspan(i, i + 1, color=PHASE_COLORS[pred_phases[i]], alpha=0.7)
    ax.set_ylabel('Predicted')
    ax.set_yticks([])

    from matplotlib.patches import Patch
    legend = [Patch(facecolor=c, label=config.PHASE_NAMES[k])
              for k, c in PHASE_COLORS.items()]
    ax.legend(handles=legend, loc='upper right', ncol=4, fontsize=8)

    # 3. Ground truth
    ax = axes[2]
    if true_labels is not None:
        for i in range(min(len(true_labels), n)):
            ax.axvspan(i, i + 1, color=PHASE_COLORS[true_labels[i]], alpha=0.7)
        ax.set_ylabel('Ground Truth')
    else:
        ax.text(0.5, 0.5, 'No ground truth', ha='center', va='center',
               transform=ax.transAxes, color='gray')
    ax.set_yticks([])
    ax.set_xlabel('Frame')

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  Сохранено: {save_path}")
    plt.close()


def plot_training_history(history, title="Training", save_path=None):
    """График истории обучения."""
    fig, axes = plt.subplots(1, len(history), figsize=(6 * len(history), 5))
    if len(history) == 1:
        axes = [axes]

    for ax, (name, values) in zip(axes, history.items()):
        ax.plot(values, linewidth=2)
        ax.set_title(name)
        ax.set_xlabel('Epoch')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  Сохранено: {save_path}")
    plt.close()


def plot_feature_importance(importances, save_path=None):
    """График важности признаков по группам и отдельно."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))

    # По группам
    groups = {}
    for name, (start, end) in config.FEATURE_GROUPS.items():
        groups[name] = importances[start:end].sum()

    total = sum(groups.values()) + 1e-8
    sorted_groups = sorted(groups.items(), key=lambda x: -x[1])
    names = [g[0].replace('_', ' ').title() for g in sorted_groups]
    values = [g[1] / total * 100 for g in sorted_groups]

    ax1.barh(range(len(names)), values, color='steelblue')
    ax1.set_yticks(range(len(names)))
    ax1.set_yticklabels(names, fontsize=9)
    ax1.set_xlabel('Importance (%)')
    ax1.set_title('Feature Groups')
    ax1.invert_yaxis()

    # Топ-15 отдельных
    top_idx = np.argsort(importances)[::-1][:15]
    top_names = [config.FEATURE_NAMES[i] if i < len(config.FEATURE_NAMES)
                 else f'f_{i}' for i in top_idx]
    top_vals = [importances[i] * 100 for i in top_idx]

    ax2.barh(range(len(top_names)), top_vals, color='coral')
    ax2.set_yticks(range(len(top_names)))
    ax2.set_yticklabels(top_names, fontsize=8)
    ax2.set_xlabel('Importance (%)')
    ax2.set_title('Top-15 Features')
    ax2.invert_yaxis()

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  Сохранено: {save_path}")
    plt.close()